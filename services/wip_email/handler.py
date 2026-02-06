"""
Client WIP Email Worker
Sends WIP email to selected client contacts.

GO IN → FETCH JOBS → BUILD EMAIL → SEND PER RECIPIENT → GET OUT

Triggered manually from Hub via POST.
"""

import os
from flask import jsonify

from utils.airtable import get_jobs_for_client
from utils.auth import generate_job_link
from utils.connect import PA_POSTMAN_URL, TIMEOUT
from .email import build_wip_email, SUBJECT_LINE

import httpx


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
            {"email": "sarah@sky.co.nz", "firstName": "Sarah", "accessLevel": "Client WIP"},
            ...
        ],
        "customNote": "Optional note" | null
    }

    Returns:
        Flask jsonify response
    """
    print("[wip-email] === BUILDING WIP EMAIL ===")

    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    client_code = data.get('clientCode')
    recipients = data.get('recipients', [])
    custom_note = data.get('customNote')

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

    # 2. Check Postman is configured
    if not PA_POSTMAN_URL:
        print("[wip-email] ERROR: PA_POSTMAN_URL not configured")
        return jsonify({'success': False, 'error': 'PA_POSTMAN_URL not configured'}), 500

    # 3. Send to each recipient
    results = []
    all_jobs = (
        jobs.get('with_hunch', []) +
        jobs.get('with_you', []) +
        jobs.get('on_hold', []) +
        jobs.get('upcoming', [])
    )

    for recipient in recipients:
        email = recipient.get('email')
        first_name = recipient.get('firstName', 'there')
        access_level = recipient.get('accessLevel', 'Client WIP')

        if not email:
            results.append({'email': email, 'success': False, 'error': 'No email'})
            continue

        print(f"[wip-email] Building for {email} ({access_level})...")

        # Generate job links with this recipient's token
        job_links = {}
        for job in all_jobs:
            job_number = job.get('jobNumber')
            if job_number:
                job_links[job_number] = generate_job_link(
                    job_number=job_number,
                    email=email,
                    client_code=client_code,
                    first_name=first_name,
                    access_level=access_level
                )

        # Build email HTML
        email_html = build_wip_email(
            jobs=jobs,
            job_links=job_links,
            first_name=first_name,
            custom_note=custom_note
        )

        # Send via Postman
        payload = {
            'to': email,
            'subject': SUBJECT_LINE,
            'body': email_html
        }

        try:
            response = httpx.post(PA_POSTMAN_URL, json=payload, timeout=TIMEOUT)
            success = response.status_code in [200, 202]
            print(f"[wip-email] Sent to {email}: {response.status_code}")
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
