"""
Setup Service
Creates new jobs from email briefs.

GO IN → EXTRACT BRIEF → CREATE JOB → CREATE UPDATE → SEND CONFIRMATION → GET OUT

Steps:
1. Get email body from Traffic table
2. Claude extracts brief details
3. Reserve job number
4. Create Project record
5. Create Dropbox job folder
6. Create Tracker record ($5K ballpark default)
7. Write first Update (state of play)
8. Send confirmation email
"""

from flask import jsonify
from anthropic import Anthropic
import httpx
import json
import os
from datetime import datetime, timedelta

from utils import airtable, connect, file

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


def _format_state_of_play(brief, job_number):
    """
    Build the first Update - state of play with visible gaps.
    Uses markdown-style formatting.
    """
    lines = []
    
    # What's the job?
    lines.append("**What's the job?**")
    lines.append(brief.get('theJob', 'TBC'))
    lines.append("")
    
    # Key details
    lines.append(f"**Owner:** {brief.get('owner', 'TBC')}")
    lines.append(f"**Live:** {brief.get('when', 'TBC')}")
    lines.append(f"**Budget:** $5K (ballpark)")
    lines.append("")
    
    # Strategic context (Who/What/Why) - only if at least one is filled
    who = brief.get('who', 'TBC')
    what = brief.get('what', 'TBC')
    why = brief.get('why', 'TBC')
    
    if who != 'TBC' or what != 'TBC' or why != 'TBC':
        lines.append("**The Customer**")
        lines.append(f"Who: {who}")
        lines.append(f"What: {what}")
        lines.append(f"Why: {why}")
        lines.append("")
    
    # Other notes
    other = brief.get('other')
    if other:
        lines.append(f"**Notes:** {other}")
        lines.append("")
    
    # Questions to resolve
    questions = brief.get('questions', [])
    if questions:
        lines.append("**To resolve:**")
        for q in questions:
            lines.append(f"- {q}")
    
    return "\n".join(lines)


# ===================
# MAIN HANDLER
# ===================

def process_setup(data):
    """
    Set up a new job from an email brief OR a Hub form submission.
    
    TWO ENTRY POINTS:
    - Email: Has internetMessageId → fetch email, Claude extracts brief
    - Hub form: Has brief directly → use it, skip Claude
    
    THEN SAME FLOW:
    1. Reserve job number
    2. Create Project record
    3. Create Dropbox job folder
    4. Create Tracker record ($5K ballpark)
    5. Write first Update (state of play)
    6. Send confirmation email
    """
    client_code = data.get('clientCode', '')
    client_name = data.get('clientName', '')
    internet_message_id = data.get('internetMessageId', '')
    sender_email = data.get('senderEmail', '')
    sender_name = data.get('senderName', '')
    subject_line = data.get('subjectLine', '')
    provided_brief = data.get('brief')  # Hub form provides this directly
    
    print(f"[setup] === PROCESSING ===")
    print(f"[setup] Client: {client_code} ({client_name})")
    print(f"[setup] Sender: {sender_email}")
    print(f"[setup] Mode: {'Hub form' if provided_brief else 'Email'}")
    
    # Track results for each step
    results = {
        'brief': None,
        'project': None,
        'dropbox': None,
        'tracker': None,
        'update': None,
        'email': None
    }
    
    # ===================
    # VALIDATE
    # ===================
    if not client_code:
        return jsonify({'success': False, 'error': 'No client code provided'}), 400
    
    # Need either internetMessageId (email) or brief (Hub form)
    if not internet_message_id and not provided_brief:
        return jsonify({'success': False, 'error': 'No internetMessageId or brief provided'}), 400
    
    try:
        # ===================
        # GET BRIEF (two paths)
        # ===================
        if provided_brief:
            # Hub form - brief provided directly
            print(f"[setup] Using provided brief from Hub form")
            brief = provided_brief
            email_body = None  # No email body for Hub submissions
        else:
            # Email - get body from payload first, fallback to Airtable
            print(f"[setup] Getting email body...")
            email_body = data.get('emailContent') or airtable.get_email_body(internet_message_id)
            
            if not email_body:
                error_msg = 'No email body in payload or Traffic table'
                print(f"[setup] {error_msg}")
                connect.send_failure(
                    to_email=sender_email, route='setup', error_message=error_msg,
                    sender_name=sender_name, subject_line=subject_line
                )
                return jsonify({'success': False, 'error': error_msg, 'results': results}), 400
            
            print(f"[setup] Email body: {len(email_body)} chars")
            
            # Claude extracts brief
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
        
        live_date = brief.get('when') or 'Tbc'
        
        project_record_id, project_error = airtable.create_project(
            job_number=job_number,
            job_name=job_name,
            description=description,
            owner=owner,
            stage='Triage',
            status='Incoming',
            update_due=update_due,
            live_date=live_date
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
        # 5. CREATE DROPBOX JOB FOLDER
        # ===================
        print(f"[setup] Creating Dropbox folder...")
        
        dropbox_url = None
        folder_result = file.create_job_folder(client_code, job_number, job_name)
        
        if folder_result.get('success'):
            dropbox_url = folder_result.get('dropboxUrl')
            results['dropbox'] = {'success': True, 'url': dropbox_url}
            print(f"[setup] Dropbox folder created: {dropbox_url}")
            
            # Write Dropbox URL to Files Url field
            airtable.update_project(project_record_id, files_url=dropbox_url)
        else:
            print(f"[setup] Dropbox folder failed (non-fatal): {folder_result.get('error')}")
            results['dropbox'] = {'success': False, 'error': folder_result.get('error')}
        
        # ===================
        # 6. CREATE TRACKER ($5K BALLPARK)
        # ===================
        print(f"[setup] Creating tracker record...")
        
        tracker_record_id, tracker_error = airtable.create_tracker(
            project_record_id=project_record_id,
            spend=5000,
            spend_type='Project budget',
            notes=brief.get('theJob'),
            ballpark=True
        )
        
        if tracker_error:
            print(f"[setup] Tracker error (non-fatal): {tracker_error}")
            results['tracker'] = {'success': False, 'error': tracker_error}
        else:
            results['tracker'] = {'success': True, 'recordId': tracker_record_id}
            print(f"[setup] Tracker created: {tracker_record_id}")
        
        # ===================
        # 7. WRITE FIRST UPDATE (STATE OF PLAY)
        # ===================
        print(f"[setup] Writing first update...")
        
        state_of_play = _format_state_of_play(brief, job_number)
        update_record_id, update_error = airtable.write_update(project_record_id, state_of_play, update_due)
        
        if update_error:
            print(f"[setup] Update error (non-fatal): {update_error}")
            results['update'] = {'success': False, 'error': update_error}
        else:
            results['update'] = {'success': True, 'recordId': update_record_id}
            print(f"[setup] Update created: {update_record_id}")
        
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
        
        # Job Bag URL
        job_number_url = job_number.replace(' ', '')  # "SKY 025" -> "SKY025"
        job_bag_url = f"https://dot.hunch.co.nz/?job={job_number_url}"
        
        email_result = connect.send_setup_confirmation(
            to_email=sender_email,
            sender_name=sender_name,
            job_number=job_number,
            job_name=job_name,
            job_bag_url=job_bag_url,
            files_url=dropbox_url,
            subject_line=subject_line,
            original_email=original_email,
            brief=brief,
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
