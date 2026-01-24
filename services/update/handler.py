"""
Update Service
Processes job updates from email content.

GO IN → DO THING → SEND COMMS → GET OUT
"""

from flask import jsonify
from anthropic import Anthropic
import httpx
import json
import os
from datetime import date, timedelta

from utils import airtable, connect

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
    UPDATE_PROMPT = f.read()


# ===================
# HELPERS
# ===================

def _strip_markdown_json(content):
    content = content.strip()
    if content.startswith('```'):
        content = content.split('\n', 1)[1] if '\n' in content else content[3:]
    if content.endswith('```'):
        content = content.rsplit('```', 1)[0]
    return content.strip()


def _get_working_days_from_today(days=5):
    current = date.today()
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current.isoformat()


# ===================
# MAIN HANDLER
# ===================

def process_update(data):
    """
    Process a job update.
    
    1. Get email body from Traffic table
    2. Look up job
    3. Claude extracts update
    4. Write to Airtable
    5. Post to Teams
    6. Send confirmation
    """
    job_number = data.get('jobNumber', '')
    internet_message_id = data.get('internetMessageId', '')
    sender_email = data.get('senderEmail', '')
    sender_name = data.get('senderName', '')
    subject_line = data.get('subjectLine', '')
    team_id = data.get('teamId')
    channel_id = data.get('teamsChannelId')
    
    print(f"[update] === PROCESSING ===")
    print(f"[update] Job: {job_number}")
    print(f"[update] Sender: {sender_email}")
    
    # ===================
    # VALIDATE
    # ===================
    if not job_number:
        return jsonify({'success': False, 'error': 'No job number provided'}), 400
    
    if not internet_message_id:
        return jsonify({'success': False, 'error': 'No internetMessageId provided'}), 400
    
    try:
        # ===================
        # 1. GET EMAIL BODY
        # ===================
        print(f"[update] Looking up email body...")
        email_body = airtable.get_email_body(internet_message_id)
        
        if not email_body:
            error_msg = 'Could not retrieve email body from Traffic table'
            print(f"[update] {error_msg}")
            connect.send_failure(
                to_email=sender_email, route='update', error_message=error_msg,
                sender_name=sender_name, job_number=job_number, subject_line=subject_line
            )
            return jsonify({'success': False, 'error': error_msg}), 400
        
        print(f"[update] Email body: {len(email_body)} chars")
        
        # ===================
        # 2. LOOK UP JOB
        # ===================
        print(f"[update] Looking up job...")
        job_record_id, project_info, lookup_error = airtable.get_project(job_number)
        
        if lookup_error:
            print(f"[update] {lookup_error}")
            connect.send_failure(
                to_email=sender_email, route='update', error_message=lookup_error,
                sender_name=sender_name, job_number=job_number, subject_line=subject_line
            )
            return jsonify({'success': False, 'error': lookup_error})
        
        print(f"[update] Found: {project_info['projectName']}")
        
        if not team_id:
            team_id = project_info.get('teamId')
        if not channel_id:
            channel_id = project_info.get('channelId')
        
        # ===================
        # 3. CLAUDE EXTRACTS
        # ===================
        print(f"[update] Calling Claude...")
        
        today = date.today()
        context = f"""
Today's date: {today.strftime('%A, %d %B %Y')}

Current job data:
- Job Number: {job_number}
- Project Name: {project_info['projectName']}
- Stage: {project_info['stage']}
- Status: {project_info['status']}
- With Client: {project_info['withClient']}
- Current Update: {project_info['currentUpdate']}
"""
        
        response = client.messages.create(
            model='claude-sonnet-4-20250514',
            max_tokens=1500,
            temperature=0.2,
            system=UPDATE_PROMPT,
            messages=[{'role': 'user', 'content': f'{context}\n\nEmail content:\n\n{email_body}'}]
        )
        
        content = response.content[0].text
        content = _strip_markdown_json(content)
        analysis = json.loads(content)
        
        update_summary = analysis.get('updateSummary', '')
        update_due = analysis.get('updateDue') or _get_working_days_from_today(5)
        
        print(f"[update] Claude: {update_summary}")
        
        # ===================
        # 4. WRITE TO AIRTABLE
        # ===================
        print(f"[update] Writing to Airtable...")
        
        update_record_id, write_error = airtable.write_update(job_record_id, update_summary, update_due)
        
        if write_error:
            print(f"[update] {write_error}")
            connect.send_failure(
                to_email=sender_email, route='update', error_message=write_error,
                sender_name=sender_name, job_number=job_number, subject_line=subject_line
            )
            return jsonify({'success': False, 'error': write_error})
        
        print(f"[update] Written: {update_record_id}")
        
        # Update project if changed
        new_stage = analysis.get('stage')
        new_status = analysis.get('status')
        new_with_client = analysis.get('withClient')
        
        stage_changed = new_stage and new_stage != project_info['stage']
        status_changed = new_status and new_status != project_info['status']
        with_client_changed = new_with_client is not None and new_with_client != project_info['withClient']
        
        if stage_changed or status_changed or with_client_changed:
            print(f"[update] Updating project...")
            airtable.update_project(
                job_record_id,
                stage=new_stage if stage_changed else None,
                status=new_status if status_changed else None,
                with_client=new_with_client if with_client_changed else None
            )
        
        # ===================
        # 5. POST TO TEAMS
        # ===================
        teams_message = analysis.get('teamsMessage', {})
        teams_subject = teams_message.get('subject', f'UPDATE: {job_number}')
        teams_body = teams_message.get('body', update_summary)
        
        context_preview = email_body[:300] + '...' if len(email_body) > 300 else email_body
        teams_body_with_context = f"{teams_body}\n\n---\n**Original email:**\n>{context_preview}"
        
        print(f"[update] Posting to Teams...")
        teams_result = connect.post_to_teams(
            team_id=team_id, channel_id=channel_id,
            subject=teams_subject, body=teams_body_with_context, job_number=job_number
        )
        print(f"[update] Teams: {teams_result.get('success')}")
        
        # ===================
        # 6. SEND CONFIRMATION
        # ===================
        original_email = {
            'senderName': sender_name,
            'senderEmail': sender_email,
            'subject': subject_line,
            'receivedDateTime': data.get('receivedDateTime', ''),
            'content': email_body
        }
        
        print(f"[update] Sending confirmation...")
        email_result = connect.send_confirmation(
            to_email=sender_email, route='update', sender_name=sender_name,
            job_number=job_number, job_name=project_info['projectName'],
            subject_line=subject_line, original_email=original_email
        )
        print(f"[update] Email: {email_result.get('success')}")
        
        # ===================
        # DONE
        # ===================
        print(f"[update] === COMPLETE ===")
        return jsonify({
            'success': True,
            'jobNumber': job_number,
            'projectName': project_info['projectName'],
            'update': update_summary,
            'updateDue': update_due,
            'stage': new_stage,
            'status': new_status,
            'withClient': new_with_client,
            'teamsPosted': teams_result.get('success', False),
            'emailSent': email_result.get('success', False)
        })
        
    except json.JSONDecodeError as e:
        print(f"[update] JSON error: {e}")
        connect.send_failure(
            to_email=sender_email, route='update',
            error_message=f'Claude returned invalid JSON: {str(e)}',
            sender_name=sender_name, job_number=job_number, subject_line=subject_line
        )
        return jsonify({'success': False, 'error': f'Invalid JSON: {str(e)}'}), 500
        
    except Exception as e:
        print(f"[update] Error: {e}")
        import traceback
        traceback.print_exc()
        connect.send_failure(
            to_email=sender_email, route='update', error_message=str(e),
            sender_name=sender_name, job_number=job_number, subject_line=subject_line
        )
        return jsonify({'success': False, 'error': str(e)}), 500
