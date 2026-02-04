"""
TO DO Email Worker
Sends daily email with jobs due + meetings.

GO IN → FETCH DATA → BUILD EMAIL → SEND → GET OUT

Triggered by PA Todobot at 7am NZ weekdays.
"""

import os
from flask import jsonify

from utils.airtable import get_todo_jobs, get_meetings, get_next_workday
from utils.auth import generate_job_link
from utils.connect import PA_POSTMAN_URL, TIMEOUT
from .email import build_todo_email

import httpx

# ===================
# CONFIG
# ===================

# Hardcoded recipient for now (later: configurable per-person)
DEFAULT_RECIPIENT = os.environ.get('TODO_RECIPIENT', 'michael@hunch.co.nz')
DEFAULT_FIRST_NAME = 'Michael'


# ===================
# MAIN HANDLER
# ===================

def send_todo_email(data=None):
    """
    Build and send the daily TO DO email.
    
    Called via GET /todo/email
    
    Returns:
        Flask jsonify response
    """
    print("[todo] === BUILDING TO DO EMAIL ===")
    
    # 1. Fetch data
    print("[todo] Fetching jobs...")
    jobs = get_todo_jobs()
    
    print("[todo] Fetching meetings...")
    meetings = get_meetings()
    
    # Get next day label
    _, next_day_label = get_next_workday()
    
    # 2. Check if there's anything to send
    total_items = (
        len(jobs.get('today', [])) + 
        len(jobs.get('tomorrow', [])) + 
        len(jobs.get('week', [])) +
        len(meetings.get('today', [])) + 
        len(meetings.get('tomorrow', []))
    )
    
    if total_items == 0:
        print("[todo] Nothing to send - no jobs or meetings")
        return jsonify({
            'success': True,
            'sent': False,
            'reason': 'No jobs or meetings to report'
        })
    
    # 3. Generate Hub links for each job
    print("[todo] Generating job links...")
    job_links = {}
    
    all_jobs = jobs.get('today', []) + jobs.get('tomorrow', []) + jobs.get('week', [])
    for job in all_jobs:
        job_number = job.get('jobNumber')
        if job_number:
            job_links[job_number] = generate_job_link(
                job_number=job_number,
                email=DEFAULT_RECIPIENT,
                client_code='ALL',
                first_name=DEFAULT_FIRST_NAME,
                access_level='Full'
            )
    
    print(f"[todo] Generated {len(job_links)} job links")
    
    # 4. Build email HTML
    print("[todo] Building email HTML...")
    email_html = build_todo_email(
        jobs=jobs,
        meetings=meetings,
        job_links=job_links,
        next_day_label=next_day_label
    )
    
    # 5. Send via Postman
    print(f"[todo] Sending to {DEFAULT_RECIPIENT}...")
    
    if not PA_POSTMAN_URL:
        print("[todo] ERROR: PA_POSTMAN_URL not configured")
        return jsonify({
            'success': False,
            'error': 'PA_POSTMAN_URL not configured'
        }), 500
    
    payload = {
        'to': DEFAULT_RECIPIENT,
        'subject': 'TO DO',
        'body': email_html
    }
    
    try:
        response = httpx.post(PA_POSTMAN_URL, json=payload, timeout=TIMEOUT)
        success = response.status_code in [200, 202]
        
        print(f"[todo] Postman response: {response.status_code}")
        
        if success:
            return jsonify({
                'success': True,
                'sent': True,
                'to': DEFAULT_RECIPIENT,
                'jobs': {
                    'today': len(jobs.get('today', [])),
                    'tomorrow': len(jobs.get('tomorrow', [])),
                    'week': len(jobs.get('week', []))
                },
                'meetings': {
                    'today': len(meetings.get('today', [])),
                    'tomorrow': len(meetings.get('tomorrow', []))
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Postman returned {response.status_code}'
            }), 500
            
    except Exception as e:
        print(f"[todo] ERROR sending email: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
