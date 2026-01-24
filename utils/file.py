"""
Dot Workers - File Utils
SharePoint filing operations via PA Filing.

Moves attachments from -- Incoming to job folders in SharePoint.
"""

import os
import json
import httpx
from datetime import datetime

# ===================
# CONFIG
# ===================

PA_FILING_URL = os.environ.get('PA_FILING_URL', '')

# Hunch SharePoint (where Incoming folder lives)
HUNCH_SITE_URL = 'https://hunch.sharepoint.com/sites/Hunch614'
INCOMING_PATH = '/Shared Documents/-- Incoming'

TIMEOUT = 120.0  # 2 minutes for file operations


# ===================
# ROUTE TO FOLDER MAPPING
# ===================

ROUTE_TO_FOLDER = {
    'triage': 'briefs',
    'new-job': 'briefs',
    'newjob': 'briefs',
    'work-to-client': 'round',
    'feedback': 'feedback',
    'file': 'other',
    'update': 'other',
}

FOLDER_NAMES = {
    'briefs': '-- Briefs',
    'feedback': '-- Feedback',
    'other': '-- Other',
}


# ===================
# MAIN FILING FUNCTION
# ===================

def file_to_sharepoint(job_number, attachment_names, files_url, route='update',
                       folder_type=None, current_round=0,
                       email_content=None, sender_name=None, sender_email=None,
                       recipients=None, subject=None, received_datetime=None):
    """
    File attachments to SharePoint job folder.
    
    Args:
        job_number: e.g., 'LAB 055'
        attachment_names: List of filenames to move from -- Incoming
        files_url: Full SharePoint URL to job folder (from Airtable)
        route: The route type (update, feedback, etc.) - determines subfolder
        folder_type: Optional override for destination folder
        current_round: Current round number (for work-to-client)
        email_content: HTML content of email (to save as .eml)
        sender_name: For .eml file
        sender_email: For .eml file
        recipients: List of recipients for .eml
        subject: Email subject for .eml
        received_datetime: When email was received
    
    Returns:
        dict with success, filed, destination, folderUrl, filesMoved, error
    """
    
    # Handle empty attachment list
    if not attachment_names:
        return {
            'success': True,
            'filed': False,
            'message': 'No attachments to file',
            'filesMoved': []
        }
    
    # Ensure attachment_names is a list
    if isinstance(attachment_names, str):
        try:
            attachment_names = json.loads(attachment_names)
        except json.JSONDecodeError:
            attachment_names = [attachment_names] if attachment_names else []
    
    # Check we have files_url
    if not files_url:
        return {
            'success': False,
            'filed': False,
            'error': f'No job bag configured for {job_number}',
            'errorType': 'no_job_bag'
        }
    
    # Check PA Filing URL is configured
    if not PA_FILING_URL:
        print('[file] ERROR: PA_FILING_URL not configured')
        return {
            'success': False,
            'filed': False,
            'error': 'PA_FILING_URL not configured'
        }
    
    print(f'[file] === FILING ===')
    print(f'[file] Job: {job_number}')
    print(f'[file] Files: {attachment_names}')
    print(f'[file] Files URL: {files_url}')
    
    # ===================
    # PARSE FILES URL
    # ===================
    # Format: https://hunch.sharepoint.com/sites/Labour/Shared Documents/LAB 055 - Election 26
    
    try:
        if '/Shared Documents/' in files_url:
            parts = files_url.split('/Shared Documents/')
            dest_site_url = parts[0]  # https://hunch.sharepoint.com/sites/Labour
            job_folder_path = parts[1]  # LAB 055 - Election 26
        else:
            raise ValueError(f'Invalid Files URL format: {files_url}')
    except Exception as e:
        print(f'[file] Error parsing Files URL: {e}')
        return {
            'success': False,
            'filed': False,
            'error': f'Invalid Files URL format for {job_number}'
        }
    
    print(f'[file] Dest site: {dest_site_url}')
    print(f'[file] Job folder: {job_folder_path}')
    
    # ===================
    # DETERMINE DESTINATION FOLDER
    # ===================
    
    # folder_type override takes priority, then route mapping, then default
    if folder_type:
        resolved_folder = folder_type
    else:
        resolved_folder = ROUTE_TO_FOLDER.get(route, 'other')
    
    print(f'[file] Route: {route} | FolderType: {folder_type} | Resolved: {resolved_folder}')
    
    # Handle Round logic if work-to-client
    round_number = None
    if resolved_folder == 'round':
        round_number = (current_round or 0) + 1
        destination_folder = f"-- Round {round_number}"
        print(f'[file] Outgoing work - Round {round_number}')
    else:
        destination_folder = FOLDER_NAMES.get(resolved_folder, '-- Other')
    
    # ===================
    # BUILD PATHS
    # ===================
    
    dest_path = f"/Shared Documents/{job_folder_path}/{destination_folder}"
    folder_url = f"{files_url}/{destination_folder}"
    
    print(f'[file] Destination path: {dest_path}')
    print(f'[file] Folder URL: {folder_url}')
    
    # ===================
    # BUILD .EML IF WE HAVE EMAIL CONTENT
    # ===================
    
    eml_filename = ''
    eml_content = ''
    save_email = False
    
    if email_content:
        save_email = True
        eml_filename = _create_eml_filename(sender_name, received_datetime)
        eml_content = _create_eml_content(
            sender_name=sender_name,
            sender_email=sender_email,
            recipients=recipients,
            subject=subject,
            html_content=email_content,
            received_datetime=received_datetime
        )
        print(f'[file] Will save email as: {eml_filename}')
    
    # ===================
    # CALL PA FILING
    # ===================
    
    payload = {
        'sourceSiteUrl': HUNCH_SITE_URL,
        'sourcePath': INCOMING_PATH,
        'sourceFiles': attachment_names,
        'destSiteUrl': dest_site_url,
        'destPath': dest_path,
        'createFolder': True,
        'saveEmail': save_email,
        'emailFilename': eml_filename,
        'emailContent': eml_content
    }
    
    print(f'[file] Calling PA Filing...')
    print(f'[file]   Source: {HUNCH_SITE_URL}{INCOMING_PATH}')
    print(f'[file]   Dest: {dest_site_url}{dest_path}')
    print(f'[file]   Files: {attachment_names}')
    print(f'[file]   Save email: {save_email}')
    
    try:
        response = httpx.post(
            PA_FILING_URL,
            json=payload,
            timeout=TIMEOUT,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f'[file] PA response status: {response.status_code}')
        
        if response.status_code == 200:
            try:
                result = response.json()
            except:
                result = {'raw': response.text}
            
            print(f'[file] PA response: {result}')
            
            # Build files moved list
            files_moved = result.get('sourceFiles', attachment_names)
            if result.get('emailSaved'):
                files_moved = list(files_moved) + [result['emailSaved']]
            
            return {
                'success': True,
                'filed': True,
                'jobNumber': job_number,
                'destination': destination_folder,
                'destPath': dest_path,
                'folderUrl': folder_url,
                'filesUrl': files_url,
                'filesMoved': files_moved,
                'count': len(files_moved),
                'roundNumber': round_number,
                'route': route,
                'folderType': resolved_folder
            }
        else:
            error_text = response.text[:500]
            print(f'[file] PA error: {response.status_code} - {error_text}')
            return {
                'success': False,
                'filed': False,
                'error': f'PA Filing returned {response.status_code}: {error_text}'
            }
            
    except httpx.TimeoutException:
        print('[file] PA request timed out')
        return {
            'success': False,
            'filed': False,
            'error': 'PA Filing request timed out'
        }
    except Exception as e:
        print(f'[file] PA request failed: {e}')
        return {
            'success': False,
            'filed': False,
            'error': str(e)
        }


# ===================
# HELPERS
# ===================

def _create_eml_filename(sender_name, received_datetime):
    """Create filename like 'Email from Sarah - 25 Jan 2026.eml'"""
    try:
        dt = datetime.fromisoformat(received_datetime.replace('Z', '+00:00'))
        date_str = dt.strftime('%d %b %Y')
    except:
        date_str = datetime.now().strftime('%d %b %Y')
    
    # Get first name, clean up
    clean_name = sender_name.split()[0] if sender_name else 'Unknown'
    clean_name = ''.join(c for c in clean_name if c.isalnum() or c in ' -_')
    
    return f"Email from {clean_name} - {date_str}.eml"


def _create_eml_content(sender_name, sender_email, recipients, subject, html_content, received_datetime):
    """Create .eml file content"""
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
