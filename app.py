"""
Dot Workers - Flask App
Workers do the work, then communicate results.

Currently handles:
- /update - Process job updates

Future:
- /file - File attachments (move from dot-file)
- /triage - New job triage
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from anthropic import Anthropic
import httpx
import json
import os
from datetime import date, timedelta

import airtable
import connect

app = Flask(__name__)
CORS(app)

# ===================
# ANTHROPIC CLIENT
# ===================

client = Anthropic(
    api_key=os.environ.get('ANTHROPIC_API_KEY'),
    http_client=httpx.Client(timeout=60.0, follow_redirects=True)
)

# Load update prompt
PROMPT_PATH = os.path.join(os.path.dirname(__file__), 'prompts', 'update.txt')
# Fallback to old location
if not os.path.exists(PROMPT_PATH):
    PROMPT_PATH = os.path.join(os.path.dirname(__file__), 'prompt.txt')
with open(PROMPT_PATH, 'r') as f:
    UPDATE_PROMPT = f.read()


# ===================
# HELPERS
# ===================

def strip_markdown_json(content):
    """Strip markdown code blocks from Claude's JSON response"""
    content = content.strip()
    if content.startswith('```'):
        content = content.split('\n', 1)[1] if '\n' in content else content[3:]
    if content.endswith('```'):
        content = content.rsplit('```', 1)[0]
    return content.strip()


def get_working_days_from_today(days=5):
    """Calculate a date N working days from today"""
    current = date.today()
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current.isoformat()


# ===================
# UPDATE ENDPOINT
# ===================

@app.route('/update', methods=['POST'])
def update():
    """
    Process job updates.
    
    1. Receive job number + internetMessageId from Brain
    2. Look up email body from Traffic table
    3. Call Claude to analyze the update
    4. Write to Airtable (Updates table + Project record)
    5. Post to Teams
    6. Send confirmation email
    7. Return success
    """
    job_number = None
    sender_email = None
    sender_name = None
    subject_line = None
    
    try:
        data = request.get_json()
        
        # ===================
        # EXTRACT FROM PAYLOAD
        # ===================
        job_number = data.get('jobNumber', '')
        internet_message_id = data.get('internetMessageId', '')
        sender_email = data.get('senderEmail', '')
        sender_name = data.get('senderName', '')
        subject_line = data.get('subjectLine', '')
        
        # Teams info (passed from Brain)
        team_id = data.get('teamId')
        channel_id = data.get('teamsChannelId')
        
        print(f"[update] === PROCESSING ===")
        print(f"[update] Job: {job_number}")
        print(f"[update] Message ID: {internet_message_id[:50] if internet_message_id else 'None'}...")
        print(f"[update] Sender: {sender_email}")
        
        # ===================
        # VALIDATE
        # ===================
        if not job_number:
            return jsonify({
                'success': False,
                'error': 'No job number provided'
            }), 400
        
        if not internet_message_id:
            return jsonify({
                'success': False,
                'error': 'No internetMessageId provided'
            }), 400
        
        # ===================
        # STEP 1: LOOK UP EMAIL BODY
        # ===================
        print(f"[update] Looking up email body from Traffic table...")
        email_body = airtable.get_email_body(internet_message_id)
        
        if not email_body:
            error_msg = 'Could not retrieve email body from Traffic table'
            print(f"[update] {error_msg}")
            
            # Send failure email
            connect.send_failure(
                to_email=sender_email,
                route='update',
                error_message=error_msg,
                sender_name=sender_name,
                job_number=job_number,
                subject_line=subject_line
            )
            
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400
        
        print(f"[update] Email body: {len(email_body)} chars")
        
        # ===================
        # STEP 2: LOOK UP JOB
        # ===================
        print(f"[update] Looking up job in Airtable...")
        job_record_id, project_info, lookup_error = airtable.get_project(job_number)
        
        if lookup_error:
            print(f"[update] Lookup error: {lookup_error}")
            
            # Send failure email
            connect.send_failure(
                to_email=sender_email,
                route='update',
                error_message=lookup_error,
                sender_name=sender_name,
                job_number=job_number,
                subject_line=subject_line
            )
            
            return jsonify({
                'success': False,
                'error': lookup_error
            })
        
        print(f"[update] Found project: {project_info['projectName']}")
        
        # Use project's Teams info if not passed in payload
        if not team_id:
            team_id = project_info.get('teamId')
        if not channel_id:
            channel_id = project_info.get('channelId')
        
        # ===================
        # STEP 3: CALL CLAUDE
        # ===================
        print(f"[update] Calling Claude to analyze update...")
        
        today = date.today()
        current_context = f"""
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
            messages=[
                {'role': 'user', 'content': f'{current_context}\n\nEmail content:\n\n{email_body}'}
            ]
        )
        
        # Parse Claude's JSON response
        content = response.content[0].text
        content = strip_markdown_json(content)
        analysis = json.loads(content)
        
        update_summary = analysis.get('updateSummary', '')
        update_due = analysis.get('updateDue') or get_working_days_from_today(5)
        
        print(f"[update] Claude analysis: {update_summary}")
        
        # ===================
        # STEP 4: WRITE TO AIRTABLE
        # ===================
        print(f"[update] Writing update to Airtable...")
        
        update_record_id, write_error = airtable.write_update(
            job_record_id, 
            update_summary, 
            update_due
        )
        
        if write_error:
            print(f"[update] Write error: {write_error}")
            
            connect.send_failure(
                to_email=sender_email,
                route='update',
                error_message=write_error,
                sender_name=sender_name,
                job_number=job_number,
                subject_line=subject_line
            )
            
            return jsonify({
                'success': False,
                'error': write_error
            })
        
        print(f"[update] Update written: {update_record_id}")
        
        # Update project if stage/status/withClient changed
        new_stage = analysis.get('stage')
        new_status = analysis.get('status')
        new_with_client = analysis.get('withClient')
        
        stage_changed = new_stage and new_stage != project_info['stage']
        status_changed = new_status and new_status != project_info['status']
        with_client_changed = new_with_client is not None and new_with_client != project_info['withClient']
        
        if stage_changed or status_changed or with_client_changed:
            print(f"[update] Updating project record...")
            airtable.update_project(
                job_record_id,
                stage=new_stage if stage_changed else None,
                status=new_status if status_changed else None,
                with_client=new_with_client if with_client_changed else None
            )
        
        # ===================
        # STEP 5: POST TO TEAMS
        # ===================
        teams_message = analysis.get('teamsMessage', {})
        teams_subject = teams_message.get('subject', f'UPDATE: {job_number}')
        teams_body = teams_message.get('body', update_summary)
        
        # Add context from original email (truncated)
        context_preview = email_body[:300] + '...' if len(email_body) > 300 else email_body
        teams_body_with_context = f"{teams_body}\n\n---\n**Original email:**\n>{context_preview}"
        
        print(f"[update] Posting to Teams...")
        teams_result = connect.post_to_teams(
            team_id=team_id,
            channel_id=channel_id,
            subject=teams_subject,
            body=teams_body_with_context,
            job_number=job_number
        )
        print(f"[update] Teams result: {teams_result.get('success')}")
        
        # ===================
        # STEP 6: SEND CONFIRMATION EMAIL
        # ===================
        # Build original email dict for trail
        original_email = {
            'senderName': sender_name,
            'senderEmail': sender_email,
            'subject': subject_line,
            'receivedDateTime': data.get('receivedDateTime', ''),
            'content': email_body
        }
        
        print(f"[update] Sending confirmation email...")
        email_result = connect.send_confirmation(
            to_email=sender_email,
            route='update',
            sender_name=sender_name,
            job_number=job_number,
            job_name=project_info['projectName'],
            subject_line=subject_line,
            original_email=original_email
        )
        print(f"[update] Email result: {email_result.get('success')}")
        
        # ===================
        # RETURN SUCCESS
        # ===================
        print(f"[update] === COMPLETE ===")
        return jsonify({
            'success': True,
            'jobNumber': job_number,
            'projectName': project_info['projectName'],
            'update': update_summary,
            'updateDue': update_due,
            'updateRecordId': update_record_id,
            'stage': new_stage,
            'status': new_status,
            'withClient': new_with_client,
            'teamsPosted': teams_result.get('success', False),
            'emailSent': email_result.get('success', False)
        })
        
    except json.JSONDecodeError as e:
        print(f"[update] JSON decode error: {e}")
        
        if sender_email:
            connect.send_failure(
                to_email=sender_email,
                route='update',
                error_message=f'Claude returned invalid JSON: {str(e)}',
                sender_name=sender_name,
                job_number=job_number,
                subject_line=subject_line
            )
        
        return jsonify({
            'success': False,
            'error': f'Claude returned invalid JSON: {str(e)}'
        }), 500
        
    except Exception as e:
        print(f"[update] Error: {e}")
        import traceback
        traceback.print_exc()
        
        if sender_email:
            connect.send_failure(
                to_email=sender_email,
                route='update',
                error_message=str(e),
                sender_name=sender_name,
                job_number=job_number,
                subject_line=subject_line
            )
        
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ===================
# HEALTH CHECK
# ===================

@app.route('/', methods=['GET'])
@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'Dot Workers',
        'version': '1.0',
        'endpoints': ['/update', '/health']
    })


# ===================
# RUN
# ===================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
