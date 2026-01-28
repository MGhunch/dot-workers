"""
Setup Service
Creates new jobs from email briefs.

GO IN → EXTRACT BRIEF → CREATE JOB → SET UP CHANNEL → POST BRIEF → SEND CONFIRMATION → GET OUT

Steps:
1. Get email body from Traffic table
2. Claude extracts brief details
3. Reserve job number
4. Create Project record
5. Create Tracker record
6. Create Teams channel
7. Post brief to Teams
8. Send confirmation email
"""

from flask import jsonify
from anthropic import Anthropic
import httpx
import json
import os
from datetime import datetime, timedelta

from utils import airtable, connect
from utils.setup import setup_teams_channel

# ===================
# CLAUDE CLIENT
# ===================

client = Anthropic(
    api_key=os.environ.get('ANTHROPIC_API_KEY'),
    http_client=httpx.Client(timeout=60.0, follow_redirects=True)
)

# Load prompt
PROMPT_PATH = os.path.join(os.path.dirname(__file__), 'prompt.txt')
with open(PROMPT_PATH, 'r') as f:
    SETUP_PROMPT = f.read()


# ===================
# HELPERS
# ===================

def _strip_markdown_json(content):
    """Strip markdown code fences from JSON response"""
    content = content.strip()
    if content.startswith('```'):
        content = content.split('\n', 1)[1] if '\n' in content else content[3:]
    if content.endswith('```'):
        content = content.rsplit('```', 1)[0]
    return content.strip()


def _get_working_days_from_today(days=5):
    """Get date N working days from today"""
    current = datetime.today()
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current.strftime('%Y-%m-%d')


def _format_teams_brief(job_number, job_name, brief):
    """
    Format the brief for Teams posting.
    Uses the extracted brief fields, shows TBC for missing items.
    """
    sections = []
    
    # THE JOB - required
    the_job = brief.get('theJob') or f"Set up {job_name}"
    sections.append(f"**THE JOB**\n{the_job}")
    
    # THE NEED - optional
    the_need = brief.get('theNeed')
    if the_need:
        sections.append(f"**THE NEED**\n{the_need}")
    
    # WHO - optional
    who = brief.get('who')
    if who:
        sections.append(f"**WHO?**\n{who}")
    
    # WHAT - optional but show TBC if missing
    what = brief.get('what')
    if what:
        sections.append(f"**WHAT?**\n{what}")
    else:
        sections.append(f"**WHAT?**\nTBC")
    
    # WHY - optional
    why = brief.get('why')
    if why:
        sections.append(f"**WHY?**\n{why}")
    
    # WHEN - optional but show TBC if missing
    when = brief.get('when')
    if when:
        sections.append(f"**WHEN?**\n{when}")
    else:
        sections.append(f"**WHEN?**\nTBC")
    
    # COSTS - optional but show TBC if missing
    costs = brief.get('costs')
    if costs:
        sections.append(f"**COSTS**\n{costs}")
    else:
        sections.append(f"**COSTS**\nTBC - check with requestor")
    
    # OTHER - optional
    other = brief.get('other')
    if other:
        sections.append(f"**OTHER**\n{other}")
    
    return "\n\n".join(sections)


# ===================
# MAIN HANDLER
# ===================

def process_setup(data):
    """
    Set up a new job from an email brief.
    
    1. Get email body from Traffic table
    2. Claude extracts brief details
    3. Reserve job number
    4. Create Project record
    5. Create Tracker record
    6. Create Teams channel
    7. Post brief to Teams
    8. Send confirmation email
    """
    client_code = data.get('clientCode', '')
    client_name = data.get('clientName', '')
    internet_message_id = data.get('internetMessageId', '')
    sender_email = data.get('senderEmail', '')
    sender_name = data.get('senderName', '')
    subject_line = data.get('subjectLine', '')
    
    print(f"[setup] === PROCESSING ===")
    print(f"[setup] Client: {client_code} ({client_name})")
    print(f"[setup] Sender: {sender_email}")
    
    # Track results for each step
    results = {
        'brief': None,
        'project': None,
        'tracker': None,
        'channel': None,
        'teams_post': None,
        'email': None
    }
    
    # ===================
    # VALIDATE
    # ===================
    if not client_code:
        return jsonify({'success': False, 'error': 'No client code provided'}), 400
    
    if not internet_message_id:
        return jsonify({'success': False, 'error': 'No internetMessageId provided'}), 400
    
    try:
        # ===================
        # 1. GET EMAIL BODY
        # ===================
        print(f"[setup] Looking up email body...")
        email_body = airtable.get_email_body(internet_message_id)
        
        if not email_body:
            error_msg = 'Could not retrieve email body from Traffic table'
            print(f"[setup] {error_msg}")
            connect.send_failure(
                to_email=sender_email, route='setup', error_message=error_msg,
                sender_name=sender_name, subject_line=subject_line
            )
            return jsonify({'success': False, 'error': error_msg, 'results': results}), 400
        
        print(f"[setup] Email body: {len(email_body)} chars")
        
        # ===================
        # 2. CLAUDE EXTRACTS BRIEF
        # ===================
        print(f"[setup] Calling Claude to extract brief...")
        
        today = datetime.today()
        context = f"""
Today's date: {today.strftime('%A, %d %B %Y')}
Client: {client_code} ({client_name})
Sender: {sender_name} <{sender_email}>
Subject: {subject_line}
"""
        
        response = client.messages.create(
            model='claude-sonnet-4-20250514',
            max_tokens=2000,
            temperature=0.2,
            system=SETUP_PROMPT,
            messages=[{'role': 'user', 'content': f'{context}\n\nEmail content:\n\n{email_body}'}]
        )
        
        content = response.content[0].text
        content = _strip_markdown_json(content)
        brief = json.loads(content)
        
        results['brief'] = brief
        
        job_name = brief.get('jobName', 'New Job')
        owner = brief.get('owner')
        costs = brief.get('costs')
        update_due = brief.get('updateDue') or _get_working_days_from_today(5)
        
        print(f"[setup] Extracted: {job_name} (confidence: {brief.get('confidence')})")
        
        # ===================
        # 3. RESERVE JOB NUMBER
        # ===================
        print(f"[setup] Reserving job number...")
        job_number, client_record_id, team_id, reserve_error = airtable.get_next_job_number(client_code)
        
        if reserve_error:
            print(f"[setup] {reserve_error}")
            connect.send_failure(
                to_email=sender_email, route='setup', error_message=reserve_error,
                sender_name=sender_name, subject_line=subject_line
            )
            return jsonify({'success': False, 'error': reserve_error, 'results': results}), 400
        
        print(f"[setup] Reserved: {job_number}")
        
        # ===================
        # 4. CREATE PROJECT
        # ===================
        print(f"[setup] Creating project...")
        
        # Build description from brief
        description_parts = []
        if brief.get('theJob'):
            description_parts.append(brief['theJob'])
        if brief.get('what'):
            description_parts.append(brief['what'])
        description = ' | '.join(description_parts) if description_parts else None
        
        project_record_id, project_error = airtable.create_project(
            job_number=job_number,
            job_name=job_name,
            client_code=client_code,
            description=description,
            owner=owner,
            stage='Triage',
            status='Incoming',
            update_due=update_due,
            live_date='Tbc',
            ballpark=costs
        )
        
        if project_error:
            print(f"[setup] {project_error}")
            results['project'] = {'success': False, 'error': project_error}
            connect.send_failure(
                to_email=sender_email, route='setup', error_message=project_error,
                sender_name=sender_name, job_number=job_number, subject_line=subject_line
            )
            return jsonify({'success': False, 'error': project_error, 'results': results}), 400
        
        results['project'] = {'success': True, 'recordId': project_record_id}
        print(f"[setup] Project created: {project_record_id}")
        
        # ===================
        # 5. CREATE TRACKER
        # ===================
        print(f"[setup] Creating tracker record...")
        
        # Parse costs to number if present
        spend = None
        if costs:
            # Extract number from string like "$2k", "$5,000", "2000"
            import re
            cost_match = re.search(r'[\d,]+(?:\.\d+)?', costs.replace('k', '000').replace('K', '000'))
            if cost_match:
                try:
                    spend = int(float(cost_match.group().replace(',', '')))
                except ValueError:
                    pass
        
        tracker_record_id, tracker_error = airtable.create_tracker(
            project_record_id=project_record_id,
            spend=spend,
            spend_type='Project budget',
            notes=brief.get('theJob')
        )
        
        if tracker_error:
            print(f"[setup] Tracker error (non-fatal): {tracker_error}")
            results['tracker'] = {'success': False, 'error': tracker_error}
        else:
            results['tracker'] = {'success': True, 'recordId': tracker_record_id}
            print(f"[setup] Tracker created: {tracker_record_id}")
        
        # ===================
        # 6. CREATE TEAMS CHANNEL
        # ===================
        print(f"[setup] Creating Teams channel...")
        
        if not team_id:
            print(f"[setup] No Team ID for client {client_code}")
            results['channel'] = {'success': False, 'error': 'No Team ID configured', 'skipped': True}
        else:
            channel_result = setup_teams_channel(
                team_id=team_id,
                job_number=job_number,
                job_name=job_name,
                record_id=project_record_id
            )
            results['channel'] = channel_result
            
            if channel_result.get('success'):
                print(f"[setup] Channel created: {channel_result.get('channelId')}")
            else:
                print(f"[setup] Channel error: {channel_result.get('error')}")
        
        # ===================
        # 7. POST BRIEF TO TEAMS
        # ===================
        print(f"[setup] Posting brief to Teams...")
        
        channel_id = results.get('channel', {}).get('channelId')
        
        if not team_id or not channel_id:
            print(f"[setup] Skipping Teams post - no channel")
            results['teams_post'] = {'success': False, 'skipped': True}
        else:
            teams_subject = f"NEW: {job_number} - {job_name}"
            teams_body = _format_teams_brief(job_number, job_name, brief)
            
            teams_result = connect.post_to_teams(
                team_id=team_id,
                channel_id=channel_id,
                subject=teams_subject,
                body=teams_body,
                job_number=job_number
            )
            results['teams_post'] = teams_result
            print(f"[setup] Teams post: {teams_result.get('success')}")
        
        # ===================
        # 8. SEND CONFIRMATION EMAIL
        # ===================
        print(f"[setup] Sending confirmation...")
        
        # Build original email for reply threading
        original_email = {
            'senderName': sender_name,
            'senderEmail': sender_email,
            'subject': subject_line,
            'content': email_body
        }
        
        # Get channel URL for the email
        channel_url = results.get('channel', {}).get('channelUrl')
        
        email_result = connect.send_setup_confirmation(
            to_email=sender_email,
            sender_name=sender_name,
            job_number=job_number,
            job_name=job_name,
            channel_url=channel_url,
            subject_line=subject_line,
            original_email=original_email,
            results=results
        )
        results['email'] = email_result
        print(f"[setup] Email: {email_result.get('success')}")
        
        # ===================
        # DONE
        # ===================
        print(f"[setup] === COMPLETE ===")
        return jsonify({
            'success': True,
            'jobNumber': job_number,
            'jobName': job_name,
            'clientCode': client_code,
            'brief': brief,
            'results': results
        })
        
    except json.JSONDecodeError as e:
        print(f"[setup] JSON error: {e}")
        connect.send_failure(
            to_email=sender_email, route='setup',
            error_message=f'Claude returned invalid JSON: {str(e)}',
            sender_name=sender_name, subject_line=subject_line
        )
        return jsonify({'success': False, 'error': f'Invalid JSON: {str(e)}', 'results': results}), 500
        
    except Exception as e:
        print(f"[setup] Error: {e}")
        import traceback
        traceback.print_exc()
        connect.send_failure(
            to_email=sender_email, route='setup', error_message=str(e),
            sender_name=sender_name, subject_line=subject_line
        )
        return jsonify({'success': False, 'error': str(e), 'results': results}), 500
