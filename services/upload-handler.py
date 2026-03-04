"""
Upload Service
Direct file upload from Hub to Dropbox job folder.

Bypasses /File transfer/ — files go straight to destination subfolder.
Called directly from the Job Bag compose bar.

GO IN → DO THING → GET OUT
(No Teams post, no confirmation email — Hub handles UI feedback)
"""

from flask import jsonify, request
from utils import file as file_utils


# ===================
# MAIN HANDLER
# ===================

def process_upload(req):
    """
    Upload a file directly to a Dropbox job folder.

    Expects multipart/form-data:
        file        — the file itself
        jobNumber   — e.g. 'SKY 018'
        jobName     — e.g. 'Offboarding Journey'
        clientCode  — e.g. 'SKY'
        subfolder   — 'Briefs' | 'Workings' | 'Finals' (default: Workings)
    """

    # ===================
    # VALIDATE
    # ===================

    uploaded_file = req.files.get('file')
    if not uploaded_file:
        return jsonify({'success': False, 'error': 'No file provided'}), 400

    job_number = req.form.get('jobNumber', '').strip()
    job_name = req.form.get('jobName', '').strip()
    client_code = req.form.get('clientCode', '').strip()
    subfolder = req.form.get('subfolder', 'Workings').strip()

    if not job_number:
        return jsonify({'success': False, 'error': 'No job number provided'}), 400

    if not client_code:
        # Fall back to extracting from job number e.g. 'SKY 018' → 'SKY'
        client_code = job_number.split(' ')[0] if ' ' in job_number else job_number[:3]

    if subfolder not in ('Briefs', 'Workings', 'Finals'):
        subfolder = 'Workings'

    filename = uploaded_file.filename or 'upload'

    print(f'[upload] === UPLOADING ===')
    print(f'[upload] Job: {job_number}')
    print(f'[upload] File: {filename}')
    print(f'[upload] Destination: {subfolder}')

    # ===================
    # BUILD PATH
    # ===================

    try:
        job_folder = file_utils._build_job_folder_path(client_code, job_number, job_name)
    except ValueError as e:
        print(f'[upload] Path error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 400

    dest_path = f'{job_folder}/{subfolder}/{filename}'

    print(f'[upload] Dest: {dest_path}')

    # ===================
    # UPLOAD TO DROPBOX
    # ===================

    try:
        file_content = uploaded_file.read()

        # Use binary upload (not text)
        result = file_utils._dropbox_upload_binary(dest_path, file_content)

        print(f'[upload] ✓ Uploaded: {filename}')

        return jsonify({
            'success': True,
            'filename': filename,
            'destination': subfolder,
            'jobNumber': job_number,
            'path': dest_path,
        })

    except Exception as e:
        print(f'[upload] ✗ Failed: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500
