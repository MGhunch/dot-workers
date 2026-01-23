"""
Dot Workers - Airtable Utils
Airtable lookups for workers.

Workers need to:
- Look up email body from Traffic table
- Look up job details from Projects table
"""

import os
import httpx

# ===================
# CONFIG
# ===================

AIRTABLE_API_KEY = os.environ.get('AIRTABLE_API_KEY')
AIRTABLE_BASE_ID = os.environ.get('AIRTABLE_BASE_ID', 'app8CI7NAZqhQ4G1Y')

TRAFFIC_TABLE = 'Traffic'
PROJECTS_TABLE = 'Projects'
UPDATES_TABLE = 'Updates'

TIMEOUT = 10.0


def _headers():
    """Standard Airtable headers"""
    return {
        'Authorization': f'Bearer {AIRTABLE_API_KEY}',
        'Content-Type': 'application/json'
    }


def _url(table):
    """Build Airtable URL for a table"""
    return f'https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{table}'


# ===================
# TRAFFIC TABLE
# ===================

def get_email_body(internet_message_id):
    """
    Retrieve email body from Traffic table by internetMessageId.
    Traffic logs the full email body when it receives emails.
    
    Returns the email body string or None if not found.
    """
    if not AIRTABLE_API_KEY or not internet_message_id:
        print(f"[airtable] Missing API key or message ID")
        return None
    
    try:
        params = {
            'filterByFormula': f"{{internetMessageId}}='{internet_message_id}'",
            'maxRecords': 1
        }
        
        response = httpx.get(
            _url(TRAFFIC_TABLE), 
            headers=_headers(), 
            params=params, 
            timeout=TIMEOUT
        )
        response.raise_for_status()
        
        records = response.json().get('records', [])
        if not records:
            print(f"[airtable] No traffic record found for {internet_message_id[:50]}...")
            return None
        
        email_body = records[0]['fields'].get('EmailBody', None)
        print(f"[airtable] Found email body: {len(email_body) if email_body else 0} chars")
        return email_body
        
    except Exception as e:
        print(f"[airtable] Error getting email body: {e}")
        return None


# ===================
# PROJECTS TABLE
# ===================

def get_project(job_number):
    """
    Look up a job by job number in Projects table.
    
    Returns tuple: (record_id, project_info, error)
    """
    if not AIRTABLE_API_KEY or not job_number:
        return None, None, "Missing API key or job number"
    
    try:
        params = {
            'filterByFormula': f"{{Job Number}}='{job_number}'",
            'maxRecords': 1
        }
        
        response = httpx.get(
            _url(PROJECTS_TABLE), 
            headers=_headers(), 
            params=params, 
            timeout=TIMEOUT
        )
        response.raise_for_status()
        
        records = response.json().get('records', [])
        if not records:
            return None, None, f"Job '{job_number}' not found"
        
        record = records[0]
        record_id = record['id']
        fields = record['fields']
        
        # Extract Team ID from Channel URL
        channel_url = fields.get('Channel Url', '')
        team_id = None
        if channel_url:
            import re
            match = re.search(r'groupId=([a-f0-9-]+)', channel_url)
            if match:
                team_id = match.group(1)
        
        project_info = {
            'recordId': record_id,
            'jobNumber': job_number,
            'projectName': fields.get('Project Name', 'Unknown'),
            'stage': fields.get('Stage', 'Unknown'),
            'status': fields.get('Status', 'Unknown'),
            'withClient': fields.get('With Client?', False),
            'currentUpdate': fields.get('Update', ''),
            'channelId': fields.get('Teams Channel ID', None),
            'teamId': team_id
        }
        
        return record_id, project_info, None
        
    except Exception as e:
        return None, None, f"Error looking up job: {str(e)}"


# ===================
# UPDATES TABLE
# ===================

def write_update(job_record_id, update_text, update_due=None):
    """
    Write an update to the Updates table.
    
    Returns tuple: (record_id, error)
    """
    if not AIRTABLE_API_KEY or not job_record_id:
        return None, "Missing API key or job record ID"
    
    try:
        update_data = {
            'fields': {
                'Project Link': [job_record_id],
                'Update': update_text
            }
        }
        
        if update_due:
            update_data['fields']['Update due'] = update_due
        
        response = httpx.post(
            _url(UPDATES_TABLE), 
            headers=_headers(), 
            json=update_data, 
            timeout=TIMEOUT
        )
        response.raise_for_status()
        
        new_record = response.json()
        return new_record.get('id'), None
        
    except Exception as e:
        return None, f"Error writing update: {str(e)}"


def update_project(job_record_id, stage=None, status=None, with_client=None):
    """
    Update a project's stage/status/withClient.
    Only updates fields that are provided and different from current.
    
    Returns tuple: (success, error)
    """
    if not AIRTABLE_API_KEY or not job_record_id:
        return False, "Missing API key or job record ID"
    
    try:
        fields = {}
        if stage and stage != 'Unknown':
            fields['Stage'] = stage
        if status and status != 'Unknown':
            fields['Status'] = status
        if with_client is not None:
            fields['With Client?'] = with_client
        
        if not fields:
            return True, None  # Nothing to update
        
        response = httpx.patch(
            f"{_url(PROJECTS_TABLE)}/{job_record_id}",
            headers=_headers(),
            json={'fields': fields},
            timeout=TIMEOUT
        )
        response.raise_for_status()
        
        return True, None
        
    except Exception as e:
        return False, f"Error updating project: {str(e)}"
