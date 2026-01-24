"""
Dot Workers - File Utils
SharePoint filing operations.

TODO: Move logic from dot-file service here.
For now, this is a placeholder.
"""

import os
import httpx

# Temporary: call existing dot-file service
DOT_FILE_URL = os.environ.get('DOT_FILE_URL', 'https://dot-file.up.railway.app')

TIMEOUT = 30.0


def file_to_sharepoint(job_number, attachment_list, files_url=None):
    """
    File attachments to SharePoint.
    
    Currently calls the existing dot-file service.
    TODO: Move logic here when consolidating.
    """
    if not attachment_list:
        return {'success': True, 'message': 'No attachments to file'}
    
    payload = {
        'jobNumber': job_number,
        'attachmentList': attachment_list,
        'filesUrl': files_url
    }
    
    print(f"[file] Filing {len(attachment_list)} attachments for {job_number}")
    
    try:
        response = httpx.post(
            f"{DOT_FILE_URL}/file",
            json=payload,
            timeout=TIMEOUT
        )
        
        success = response.status_code == 200
        print(f"[file] Result: {success} ({response.status_code})")
        
        return {
            'success': success,
            'response': response.json() if success else response.text
        }
        
    except Exception as e:
        print(f"[file] Error: {e}")
        return {'success': False, 'error': str(e)}
