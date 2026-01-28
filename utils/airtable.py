"""
Dot Workers - Airtable Utils
Shared data lookups for all workers.
"""

import os
import httpx
from datetime import datetime

# ===================
# CONFIG
# ===================

AIRTABLE_API_KEY = os.environ.get('AIRTABLE_API_KEY')
AIRTABLE_BASE_ID = os.environ.get('AIRTABLE_BASE_ID', 'app8CI7NAZqhQ4G1Y')

TRAFFIC_TABLE = 'Traffic'
PROJECTS_TABLE = 'Projects'
UPDATES_TABLE = 'Updates'
CLIENTS_TABLE = 'Clients'
TRACKER_TABLE = 'Tracker'

TIMEOUT = 10.0


def _headers():
    return {
        'Authorization': f'Bearer {AIRTABLE_API_KEY}',
        'Content-Type': 'application/json'
    }


def _url(table):
    return f'https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{table}'


def _get_current_quarter():
    """Get current quarter string (e.g., 'Jan-Mar', 'Apr-Jun')"""
    month = datetime.now().month
    if month <= 3:
        return 'Jan-Mar'
    elif month <= 6:
        return 'Apr-Jun'
    elif month <= 9:
        return 'Jul-Sep'
    else:
        return 'Oct-Dec'


def _get_current_month():
    """Get current month name (e.g., 'January')"""
    return datetime.now().strftime('%B')


# ===================
# CLIENTS TABLE
# ===================

def get_client_sharepoint(client_code):
    """
    Look up SharePoint URL from Clients table by client code.
    Returns SharePoint URL string or None.
    
    The field in Airtable is called 'Sharepoint ID' and contains
    URLs like 'https://hunch.sharepoint.com/sites/OneNZ'
    """
    if not AIRTABLE_API_KEY or not client_code:
        return None
    
    try:
        params = {
            'filterByFormula': f"{{Client code}}='{client_code}'"
        }
        
        response = httpx.get(
            _url(CLIENTS_TABLE), 
            headers=_headers(), 
            params=params, 
            timeout=TIMEOUT
        )
        response.raise_for_status()
        
        records = response.json().get('records', [])
        if not records:
            print(f"[airtable] No client found for code: {client_code}")
            return None
        
        sharepoint_url = records[0]['fields'].get('Sharepoint ID', None)
        
        if not sharepoint_url:
            print(f"[airtable] No SharePoint URL configured for: {client_code}")
            
        return sharepoint_url
        
    except Exception as e:
        print(f"[airtable] Error looking up client SharePoint: {e}")
        return None


def get_next_job_number(client_code):
    """
    Get next job number for a client and increment the counter.
    
    Reads 'Next Job #' (e.g., "LAB 056") and increments 'Next #' for next time.
    
    Returns tuple: (job_number, client_record_id, team_id, error)
    - job_number: e.g., "LAB 056"
    - client_record_id: Airtable record ID for the client
    - team_id: Teams ID for this client
    - error: error message or None
    """
    if not AIRTABLE_API_KEY or not client_code:
        return None, None, None, "Missing API key or client code"
    
    try:
        params = {
            'filterByFormula': f"{{Client code}}='{client_code}'"
        }
        
        response = httpx.get(
            _url(CLIENTS_TABLE), 
            headers=_headers(), 
            params=params, 
            timeout=TIMEOUT
        )
        response.raise_for_status()
        
        records = response.json().get('records', [])
        if not records:
            return None, None, None, f"Client '{client_code}' not found"
        
        record = records[0]
        record_id = record['id']
        fields = record['fields']
        
        # Get the formatted job number (e.g., "LAB 056")
        job_number = fields.get('Next Job #', None)
        if not job_number:
            return None, None, None, f"No 'Next Job #' configured for {client_code}"
        
        # Get current counter to increment
        current_counter = fields.get('Next #', 0)
        team_id = fields.get('Teams ID', None)
        
        # Increment the counter for next time
        response = httpx.patch(
            f"{_url(CLIENTS_TABLE)}/{record_id}",
            headers=_headers(),
            json={'fields': {'Next #': current_counter + 1}},
            timeout=TIMEOUT
        )
        response.raise_for_status()
        
        print(f"[airtable] Reserved job number: {job_number}, incremented to {current_counter + 1}")
        return job_number, record_id, team_id, None
        
    except Exception as e:
        return None, None, None, f"Error reserving job number: {str(e)}"


def get_client_name(client_code):
    """
    Look up client name from Clients table by client code.
    Returns client name string or None.
    """
    if not AIRTABLE_API_KEY or not client_code:
        return None
    
    try:
        params = {
            'filterByFormula': f"{{Client code}}='{client_code}'"
        }
        
        response = httpx.get(
            _url(CLIENTS_TABLE), 
            headers=_headers(), 
            params=params, 
            timeout=TIMEOUT
        )
        response.raise_for_status()
        
        records = response.json().get('records', [])
        if not records:
            return None
        
        return records[0]['fields'].get('Clients', None)
        
    except Exception as e:
        print(f"[airtable] Error looking up client name: {e}")
        return None


# ===================
# TRAFFIC TABLE
# ===================

def get_email_body(internet_message_id):
    """
    Retrieve email body from Traffic table.
    Brain logs it there when email arrives.
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
    Look up a job by job number.
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


def create_project(job_number, job_name, client_code, description=None,
                   owner=None, stage='Triage', status='Incoming',
                   update_due=None, live_date=None, ballpark=None):
    """
    Create a new project record.
    
    Args:
        job_number: e.g., 'LAB 056'
        job_name: e.g., 'Election Campaign'
        client_code: e.g., 'LAB'
        description: job description/brief summary
        owner: client contact name
        stage: default 'Triage'
        status: default 'Incoming'
        update_due: ISO date string
        live_date: month string (e.g., 'Feb', 'Tbc')
        ballpark: budget string (e.g., '$5,000')
    
    Returns tuple: (record_id, error)
    """
    if not AIRTABLE_API_KEY:
        return None, "Missing API key"
    
    if not job_number or not job_name:
        return None, "Missing job number or job name"
    
    try:
        fields = {
            'Job Number': job_number,
            'Project Name': job_name,
            'Stage': stage,
            'Status': status,
        }
        
        # Optional fields
        if description:
            fields['Description'] = description
        if owner:
            fields['Project Owner'] = owner
        if update_due:
            fields['Update Due'] = update_due
        if live_date:
            fields['Live'] = live_date
        if ballpark:
            fields['Ballpark'] = ballpark
        
        print(f"[airtable] Creating project: {job_number} - {job_name}")
        
        response = httpx.post(
            _url(PROJECTS_TABLE),
            headers=_headers(),
            json={'fields': fields},
            timeout=TIMEOUT
        )
        response.raise_for_status()
        
        new_record = response.json()
        record_id = new_record.get('id')
        
        print(f"[airtable] Created project: {record_id}")
        return record_id, None
        
    except Exception as e:
        return None, f"Error creating project: {str(e)}"


def update_project(job_record_id, stage=None, status=None, with_client=None):
    """
    Update a project's stage/status/withClient.
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
            return True, None
        
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


# ===================
# TRACKER TABLE
# ===================

def create_tracker(project_record_id, spend=None, spend_type='Project budget',
                   month=None, quarter=None, notes=None):
    """
    Create a new tracker record linked to a project.
    
    The Link field links to Projects - most other fields are lookups from that.
    
    Args:
        project_record_id: Airtable record ID of the project
        spend: dollar amount as number (e.g., 5000) or string (e.g., '$5,000')
        spend_type: 'Project budget', 'Extra budget', or 'Project on us'
        month: e.g., 'January' (defaults to current month)
        quarter: e.g., 'Jan-Mar' (defaults to current quarter)
        notes: tracker notes
    
    Returns tuple: (record_id, error)
    """
    if not AIRTABLE_API_KEY or not project_record_id:
        return None, "Missing API key or project record ID"
    
    try:
        # Use defaults if not provided
        if not month:
            month = _get_current_month()
        if not quarter:
            quarter = _get_current_quarter()
        
        fields = {
            'Link': [project_record_id],  # Linked record to Projects
            'Spend type': spend_type,
            'Month': month,
            'Quarter': quarter,
        }
        
        # Handle spend - convert string to number if needed
        if spend:
            if isinstance(spend, str):
                # Strip $ and commas, convert to number
                spend_clean = spend.replace('$', '').replace(',', '').strip()
                try:
                    spend = int(float(spend_clean))
                except ValueError:
                    spend = None
            
            if spend:
                fields['Spend'] = f"${spend:,}"  # Format as "$5,000"
                fields['This month'] = spend  # Numeric field
        
        if notes:
            fields['Tracker notes'] = notes
        
        print(f"[airtable] Creating tracker record for project: {project_record_id}")
        
        response = httpx.post(
            _url(TRACKER_TABLE),
            headers=_headers(),
            json={'fields': fields},
            timeout=TIMEOUT
        )
        response.raise_for_status()
        
        new_record = response.json()
        record_id = new_record.get('id')
        
        print(f"[airtable] Created tracker: {record_id}")
        return record_id, None
        
    except Exception as e:
        return None, f"Error creating tracker: {str(e)}"


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
            update_data['fields']['Update Due'] = update_due
        
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
