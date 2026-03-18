"""
Client WIP Email Worker
Sends WIP email to selected client contacts.

GO IN → FETCH JOBS → BUILD EMAIL → SEND PER RECIPIENT → GET OUT

Triggered manually from Hub via POST.
"""

import os
from flask import jsonify

from utils.airtable import get_jobs_for_client
from .email import build_wip_email, get_subject_line

import httpx


# ===================
# CONFIG
# ===================

RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
RESEND_URL = 'https://api.resend.com/emails'
TIMEOUT = 30.0


# ===================
# MAIN HANDLER
# ===================

def send_wip_email(data):
    """
    Build and send WIP email to selected recipients.

    Expects POST body:
    {
        "clientCode": "SKY",
        "recipients": [
            {"email": "sarah@sky.co.nz", "firstName": "Sarah"},
            ...
        ],
        "intro": "Optional custom intro" | null,
        "senderEmail": "michael@hunch.co.nz"
    }

    Returns:
        Flask jsonify response
    """
    print("[wip-email] === BUILDING WIP EMAIL ===")

    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    client_code = data.get('clientCode')
    recipients = data.get('recipients', [])
    intro = data.get('intro')
    sender_email = data.get('senderEmail', 'dot@hunch.co.nz')

    if not client_code:
        return jsonify({'success': False, 'error': 'Missing clientCode'}), 400

    if not recipients:
        return jsonify({'success': False, 'error': 'No recipients provided'}), 400

    # 1. Fetch active jobs for this client
    print(f"[wip-email] Fetching jobs for {client_code}...")
    jobs = get_jobs_for_client(client_code)

    total_jobs = (
        len(jobs.get('with_hunch', [])) +
        len(jobs.get('with_you', [])) +
        len(jobs.get('on_hold', [])) +
        len(jobs.get('upcoming', []))
    )

    if total_jobs == 0:
        print("[wip-email] No active jobs to send")
        return jsonify({
            'success': False,
            'error': f'No active jobs found for {client_code}'
        }), 400

    print(f"[wip-email] Found {total_jobs} jobs")

    # 2. Check Resend is configured
    if not RESEND_API_KEY:
        print("[wip-email] ERROR: RESEND_API_KEY not configured")
        return jsonify({'success': False, 'error': 'RESEND_API_KEY not configured'}), 500

    # 3. Build job links (same for all recipients)
    all_jobs = (
        jobs.get('with_hunch', []) +
        jobs.get('with_you', []) +
        jobs.get('on_hold', []) +
        jobs.get('upcoming', [])
    )

    job_links = {}
    for job in all_jobs:
        job_number = job.get('jobNumber')
        if job_number:
            job_links[job_number] = f"https://dot.hunch.co.nz/job/{job_number}"

    # 4. Send to each recipient
    results = []

    for recipient in recipients:
        email = recipient.get('email')
        first_name = recipient.get('firstName', 'there')

        if not email:
            results.append({'email': email, 'success': False, 'error': 'No email'})
            continue

        print(f"[wip-email] Building for {email}...")

        # Build email HTML
        email_html = build_wip_email(
            jobs=jobs,
            job_links=job_links,
            first_name=first_name,
            intro=intro
        )

        # Send via Resend
        payload = {
            'from': sender_email,
            'to': [email],
            'subject': get_subject_line(client_code),
            'html': email_html
        }

        try:
            response = httpx.post(
                RESEND_URL,
                headers={
                    'Authorization': f'Bearer {RESEND_API_KEY}',
                    'Content-Type': 'application/json'
                },
                json=payload,
                timeout=TIMEOUT
            )
            success = response.status_code == 200
            print(f"[wip-email] Sent to {email}: {response.status_code}")
            if not success:
                print(f"[wip-email] Response: {response.text}")
            results.append({'email': email, 'success': success})
        except Exception as e:
            print(f"[wip-email] ERROR sending to {email}: {e}")
            results.append({'email': email, 'success': False, 'error': str(e)})

    # 4. Summarise
    sent = sum(1 for r in results if r.get('success'))
    failed = len(results) - sent

    print(f"[wip-email] Done: {sent}/{len(results)} sent")

    return jsonify({
        'success': failed == 0,
        'sent': sent,
        'failed': failed,
        'total_jobs': total_jobs,
        'results': results
    })
