"""
Dot Workers - File Utils
Dropbox filing operations via API.

Moves attachments from /File transfer/ to job folders in Dropbox.
"""

import os
import re
import json
import time
import httpx
from datetime import datetime

# ===================
# CONFIG
# ===================

DROPBOX_APP_KEY = os.environ.get('DROPBOX_APP_KEY', '')
DROPBOX_APP_SECRET = os.environ.get('DROPBOX_APP_SECRET', '')
DROPBOX_REFRESH_TOKEN = os.environ.get('DROPBOX_REFRESH_TOKEN', '')

FILE_TRANSFER_PATH = '/File transfer'

TIMEOUT = 120.0  # 2 minutes for file operations

# Token cache (module-level)
_access_token = None
_token_expires_at = 0


# ===================
# CLIENT CODE → DROPBOX PATH
# ===================

CLIENT_PATHS = {
    # Main clients
    'SKY': 'Clients/Sky',
    'TOW': 'Clients/Tower',
    'FIS': 'Clients/Fisher Funds',
    'ONE': 'Clients/One NZ/Marketing',
    'ONS': 'Clients/One NZ/Simplification',
    'ONB': 'Clients/One NZ/Business',
    'HUN': 'Clients/Hunch',
    # Other clients
    'LAB': 'Clients/Other/Labour',
    'FST': 'Clients/Other/Firestop',
    'EON': 'Clients/Other/Eon Fibre',
    'WKA': 'Clients/Other/Waikato',
}


# ===================
# ROUTE TO SUBFOLDER
# ===================

ROUTE_TO_SUBFOLDER = {
    'triage': 'Briefs',
    'new-job': 'Briefs',
    'newjob': 'Briefs',
    'setup': 'Briefs',
}

# Everything not in ROUTE_TO_SUBFOLDER goes to 'Workings'
DEFAULT_SUBFOLDER = 'Workings'


# ===================
# DROPBOX AUTH
# ===================

def _get_access_token():
    """Get a fresh Dropbox access token using refresh token. Caches until near expiry."""
    global _access_token, _token_expires_at

    # Return cached token if still valid (with 5 min buffer)
    if _access_token and time.time() < (_token_expires_at - 300):
        return _access_token

    if not all([DROPBOX_APP_KEY, DROPBOX_APP_SECRET, DROPBOX_REFRESH_TOKEN]):
        raise ValueError('Dropbox credentials not configured (need APP_KEY, APP_SECRET, REFRESH_TOKEN)')

    print('[file] Refreshing Dropbox access token...')

    response = httpx.post(
        'https://api.dropbox.com/oauth2/token',
        data={
            'grant_type': 'refresh_token',
            'refresh_token': DROPBOX_REFRESH_TOKEN,
            'client_id': DROPBOX_APP_KEY,
            'client_secret': DROPBOX_APP_SECRET,
        },
        timeout=30.0
    )

    if response.status_code != 200:
        raise ValueError(f'Dropbox token refresh failed: {response.status_code} - {response.text[:200]}')

    result = response.json()
    _access_token = result['access_token']
    _token_expires_at = time.time() + result.get('expires_in', 14400)

    print('[file] Dropbox token refreshed OK')
    return _access_token


def _dropbox_headers():
    """Get auth headers for Dropbox API calls."""
    token = _get_access_token()
    return {'Authorization': f'Bearer {token}'}


# ===================
# DROPBOX API HELPERS
# ===================

def _dropbox_move(from_path, to_path):
    """Move a file within Dropbox. Creates destination folder if needed."""
    response = httpx.post(
        'https://api.dropboxapi.com/2/files/move_v2',
        headers={**_dropbox_headers(), 'Content-Type': 'application/json'},
        json={
            'from_path': from_path,
            'to_path': to_path,
            'autorename': True,
        },
        timeout=TIMEOUT
    )

    if response.status_code == 200:
        return response.json()

    # If destination folder doesn't exist, create it and retry
    if response.status_code == 409:
        error_data = response.json()
        error_tag = error_data.get('error', {}).get('.tag', '')

        if error_tag == 'to' or 'not_found' in str(error_data):
            dest_folder = '/'.join(to_path.rsplit('/', 1)[:-1])
            _dropbox_create_folder(dest_folder)

            # Retry move
            retry = httpx.post(
                'https://api.dropboxapi.com/2/files/move_v2',
                headers={**_dropbox_headers(), 'Content-Type': 'application/json'},
                json={
                    'from_path': from_path,
                    'to_path': to_path,
                    'autorename': True,
                },
                timeout=TIMEOUT
            )
            if retry.status_code == 200:
                return retry.json()
            raise ValueError(f'Dropbox move retry failed: {retry.status_code} - {retry.text[:200]}')

    raise ValueError(f'Dropbox move failed: {response.status_code} - {response.text[:200]}')


def _dropbox_create_folder(path):
    """Create a folder in Dropbox (no error if it already exists)."""
    response = httpx.post(
        'https://api.dropboxapi.com/2/files/create_folder_v2',
        headers={**_dropbox_headers(), 'Content-Type': 'application/json'},
        json={'path': path, 'autorename': False},
        timeout=TIMEOUT
    )

    # 200 = created, 409 = already exists (both fine)
    if response.status_code in (200, 409):
        return True

    raise ValueError(f'Dropbox create folder failed: {response.status_code} - {response.text[:200]}')


def _dropbox_upload(path, content):
    """Upload content as a file to Dropbox."""
    response = httpx.post(
        'https://content.dropboxapi.com/2/files/upload',
        headers={
            **_dropbox_headers(),
            'Content-Type': 'application/octet-stream',
            'Dropbox-API-Arg': json.dumps({
                'path': path,
                'mode': 'add',
                'autorename': True,
            })
        },
        content=content.encode('utf-8'),
        timeout=TIMEOUT
    )

    if response.status_code == 200:
        return response.json()

    raise ValueError(f'Dropbox upload failed: {response.status_code} - {response.text[:200]}')


def _dropbox_list_folder(path):
    """List files in a Dropbox folder."""
    response = httpx.post(
        'https://api.dropboxapi.com/2/files/list_folder',
        headers={**_dropbox_headers(), 'Content-Type': 'application/json'},
        json={'path': path},
        timeout=TIMEOUT
    )

    if response.status_code == 200:
        return response.json().get('entries', [])

    raise ValueError(f'Dropbox list folder failed: {response.status_code} - {response.text[:200]}')


# ===================
# FILENAME HELPERS
# ===================

def _strip_timestamp_prefix(filename):
    """
    Strip PA timestamp prefix from filename.
    '20260208-185823_BroadbandBrief.pdf' → 'BroadbandBrief.pdf'
    """
    match = re.match(r'^\d{8}-\d{6}_(.+)$', filename)
    return match.group(1) if match else filename


def _find_file_in_transfer(attachment_name, transfer_files):
    """
    Find a file in /File transfer/ that matches the attachment name.
    Matches against the original name (after stripping timestamp prefix).
    Returns the full Dropbox filename or None.
    """
    for entry in transfer_files:
        if entry.get('.tag') != 'file':
            continue
        name = entry.get('name', '')
        if _strip_timestamp_prefix(name) == attachment_name:
            return name
        # Also match exact name (in case no prefix)
        if name == attachment_name:
            return name
    return None


# ===================
# PATH BUILDER
# ===================

def _build_job_folder_path(client_code, job_number, job_name):
    """
    Build the Dropbox path to a job folder.
    e.g. '/Clients/Sky/Active/SKY 018 - Broadband Launch'
    """
    client_path = CLIENT_PATHS.get(client_code)
    if not client_path:
        raise ValueError(f'Unknown client code: {client_code}')

    # Clean job name for folder safety
    clean_name = job_name.strip() if job_name else 'Untitled'
    clean_name = re.sub(r'[<>:"/\\|?*]', '', clean_name)

    return f'/{client_path}/Active/{job_number} - {clean_name}'


# ===================
# MAIN FILING FUNCTION
# ===================

def file_to_dropbox(job_number, attachment_names, client_code, job_name,
                    route='update', project_record_id=None,
                    email_content=None, sender_name=None, sender_email=None,
                    recipients=None, subject=None, received_datetime=None):
    """
    File attachments to Dropbox job folder.

    Moves files from /File transfer/ to the correct job subfolder,
    stripping PA timestamp prefixes on the way.

    Args:
        job_number: e.g. 'SKY 018'
        attachment_names: List of original filenames to find in /File transfer/
        client_code: e.g. 'SKY' — used to resolve Dropbox path
        job_name: e.g. 'Broadband Launch' — used for folder name
        route: Route type — triage/new-job/setup → Briefs, everything else → Workings
        project_record_id: Airtable record ID — if provided, updates Files Url
        email_content: HTML content of email (to save as .eml)
        sender_name: For .eml file
        sender_email: For .eml file
        recipients: List of recipients for .eml
        subject: Email subject for .eml
        received_datetime: When email was received

    Returns:
        dict with success, filed, destination, filesMoved, error
    """

    # Handle empty attachment list (but still save .eml if provided)
    if not attachment_names and not email_content:
        return {
            'success': True,
            'filed': False,
            'message': 'No attachments to file',
            'filesMoved': []
        }

    # Ensure attachment_names is a list
    if not attachment_names:
        attachment_names = []
    elif isinstance(attachment_names, str):
        try:
            attachment_names = json.loads(attachment_names)
        except json.JSONDecodeError:
            attachment_names = [attachment_names] if attachment_names else []

    print(f'[file] === FILING (Dropbox) ===')
    print(f'[file] Job: {job_number}')
    print(f'[file] Client: {client_code}')
    print(f'[file] Files: {attachment_names}')
    print(f'[file] Route: {route}')

    # ===================
    # BUILD PATHS
    # ===================

    try:
        job_folder = _build_job_folder_path(client_code, job_number, job_name)
    except ValueError as e:
        print(f'[file] Path error: {e}')
        return {
            'success': False,
            'filed': False,
            'error': str(e)
        }

    subfolder = ROUTE_TO_SUBFOLDER.get(route, DEFAULT_SUBFOLDER)
    dest_path = f'{job_folder}/{subfolder}'

    print(f'[file] Job folder: {job_folder}')
    print(f'[file] Destination: {dest_path}')

    # ===================
    # LIST /File transfer/ TO FIND MATCHING FILES
    # ===================

    files_moved = []
    errors = []

    if attachment_names:
        try:
            transfer_files = _dropbox_list_folder(FILE_TRANSFER_PATH)
            print(f'[file] Files in transfer: {len(transfer_files)}')
        except Exception as e:
            print(f'[file] Error listing File transfer: {e}')
            return {
                'success': False,
                'filed': False,
                'error': f'Could not list File transfer folder: {e}'
            }

        # ===================
        # MOVE EACH FILE
        # ===================

        for attachment_name in attachment_names:
            transfer_name = _find_file_in_transfer(attachment_name, transfer_files)

            if not transfer_name:
                print(f'[file] NOT FOUND in transfer: {attachment_name}')
                errors.append(f'Not found: {attachment_name}')
                continue

            from_path = f'{FILE_TRANSFER_PATH}/{transfer_name}'
            clean_name = _strip_timestamp_prefix(transfer_name)
            to_path = f'{dest_path}/{clean_name}'

            try:
                print(f'[file] Moving: {from_path} → {to_path}')
                _dropbox_move(from_path, to_path)
                files_moved.append(clean_name)
                print(f'[file] ✓ Moved: {clean_name}')
            except Exception as e:
                print(f'[file] ✗ Failed to move {transfer_name}: {e}')
                errors.append(f'Move failed: {attachment_name} - {e}')

    # ===================
    # SAVE .EML IF WE HAVE EMAIL CONTENT
    # ===================

    if email_content:
        eml_filename = _create_eml_filename(sender_name, received_datetime)
        eml_content = _create_eml_content(
            sender_name=sender_name,
            sender_email=sender_email,
            recipients=recipients,
            subject=subject,
            html_content=email_content,
            received_datetime=received_datetime
        )

        eml_path = f'{dest_path}/{eml_filename}'

        try:
            print(f'[file] Uploading .eml: {eml_path}')
            _dropbox_upload(eml_path, eml_content)
            files_moved.append(eml_filename)
            print(f'[file] ✓ Saved: {eml_filename}')
        except Exception as e:
            print(f'[file] ✗ Failed to save .eml: {e}')
            errors.append(f'EML save failed: {e}')

    # ===================
    # UPDATE AIRTABLE FILES URL
    # ===================

    dropbox_url = f'https://www.dropbox.com/home{job_folder}'

    if project_record_id and files_moved:
        try:
            from utils.airtable import update_project
            update_project(project_record_id, files_url=dropbox_url)
            print(f'[file] ✓ Updated Files Url: {dropbox_url}')
        except Exception as e:
            print(f'[file] ✗ Failed to update Files Url: {e}')
            # Don't fail the whole operation for this

    # ===================
    # RESULT
    # ===================

    success = len(files_moved) > 0
    filed = len(files_moved) > 0

    if errors and not files_moved:
        return {
            'success': False,
            'filed': False,
            'error': '; '.join(errors),
            'filesMoved': []
        }

    result = {
        'success': success,
        'filed': filed,
        'jobNumber': job_number,
        'destination': subfolder,
        'jobFolder': job_folder,
        'dropboxUrl': dropbox_url,
        'filesMoved': files_moved,
        'count': len(files_moved),
        'route': route,
    }

    if errors:
        result['warnings'] = errors

    print(f'[file] === DONE === Filed {len(files_moved)} file(s) to {subfolder}')
    return result


# ===================
# JOB FOLDER CREATION (for Setup worker)
# ===================

def create_job_folder(client_code, job_number, job_name):
    """
    Create a new job folder with subfolders in Dropbox.
    Called by Setup worker after creating the Project record.

    Returns the Dropbox URL for the job folder (to write to Files Url).
    """
    try:
        job_folder = _build_job_folder_path(client_code, job_number, job_name)
    except ValueError as e:
        print(f'[file] Path error: {e}')
        return {'success': False, 'error': str(e)}

    print(f'[file] Creating job folder: {job_folder}')

    try:
        _dropbox_create_folder(job_folder)
        _dropbox_create_folder(f'{job_folder}/Briefs')
        _dropbox_create_folder(f'{job_folder}/Finals')
        _dropbox_create_folder(f'{job_folder}/Workings')

        dropbox_url = f'https://www.dropbox.com/home{job_folder}'

        print(f'[file] ✓ Created: {job_folder}')
        return {
            'success': True,
            'jobFolder': job_folder,
            'dropboxUrl': dropbox_url,
        }

    except Exception as e:
        print(f'[file] ✗ Failed to create folder: {e}')
        return {'success': False, 'error': str(e)}


# ===================
# EML HELPERS
# ===================

def _create_eml_filename(sender_name, received_datetime):
    """Create filename like 'Email from Sarah - 25 Jan 2026.eml'"""
    try:
        dt = datetime.fromisoformat(received_datetime.replace('Z', '+00:00'))
        date_str = dt.strftime('%d %b %Y')
    except:
        date_str = datetime.now().strftime('%d %b %Y')

    clean_name = sender_name.split()[0] if sender_name else 'Unknown'
    clean_name = ''.join(c for c in clean_name if c.isalnum() or c in ' -_')

    return f'Email from {clean_name} - {date_str}.eml'


def _create_eml_content(sender_name, sender_email, recipients, subject, html_content, received_datetime):
    """Create .eml file content."""
    recipient_str = ', '.join(recipients) if recipients else ''

    try:
        dt = datetime.fromisoformat(received_datetime.replace('Z', '+00:00'))
        email_date = dt.strftime('%a, %d %b %Y %H:%M:%S %z')
    except:
        email_date = received_datetime or ''

    return f"""MIME-Version: 1.0
Date: {email_date}
From: {sender_name or 'Unknown'} <{sender_email or ''}>
To: {recipient_str}
Subject: {subject or ''}
Content-Type: text/html; charset="utf-8"

{html_content or ''}
"""
