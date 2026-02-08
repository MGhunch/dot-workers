"""
Dot Workers - Setup Utils
Teams channel creation via PA Setupbot.
"""

import os
import httpx

from utils.airtable import _headers, _url, PROJECTS_TABLE

PA_SETUPBOT_URL = os.environ.get('PA_SETUPBOT_URL', '')
TIMEOUT = 30.0  # Channel creation might take a few seconds


def setup_teams_channel(team_id, job_number, job_name, record_id):
    """
    Create Teams channel for a job and save URLs to Airtable.
    
    Note: Files Url is now handled by Dropbox folder creation in the setup handler.
    This function only writes Teams Channel ID and Channel Url.
    
    Args:
        team_id: Teams team ID (from Clients table)
        job_number: e.g., 'LAB 055'
        job_name: e.g., 'Campaign Refresh'
        record_id: Airtable Projects record ID
    
    Returns:
        dict with success, channelId, channelUrl, error
    """
    
    if not PA_SETUPBOT_URL:
        print('[setup] ERROR: PA_SETUPBOT_URL not configured')
        return {'success': False, 'error': 'PA_SETUPBOT_URL not configured'}
    
    if not team_id:
        print('[setup] ERROR: No team_id provided')
        return {'success': False, 'error': 'No team_id provided'}
    
    # Build channel name: "LAB 055 - Campaign Refresh"
    channel_name = f"{job_number} - {job_name}"
    
    print(f'[setup] === SETUP TEAMS CHANNEL ===')
    print(f'[setup] Team ID: {team_id}')
    print(f'[setup] Channel name: {channel_name}')
    print(f'[setup] Record ID: {record_id}')
    
    # ===================
    # CALL PA SETUPBOT
    # ===================
    
    try:
        response = httpx.post(
            PA_SETUPBOT_URL,
            json={
                'teamId': team_id,
                'channelName': channel_name
            },
            timeout=TIMEOUT,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f'[setup] PA response status: {response.status_code}')
        
        if response.status_code != 200:
            error_text = response.text[:500]
            print(f'[setup] PA error: {error_text}')
            return {'success': False, 'error': f'PA Setupbot returned {response.status_code}'}
        
        result = response.json()
        print(f'[setup] PA response: {result}')
        
        if not result.get('success'):
            return {'success': False, 'error': result.get('error', 'Unknown PA error')}
        
        channel_id = result.get('channelId')
        channel_url = result.get('channelUrl')
        
    except httpx.TimeoutException:
        print('[setup] PA request timed out')
        return {'success': False, 'error': 'PA Setupbot request timed out'}
    except Exception as e:
        print(f'[setup] PA request failed: {e}')
        return {'success': False, 'error': str(e)}
    
    # ===================
    # PATCH AIRTABLE (Teams fields only — Files Url handled by Dropbox)
    # ===================
    
    try:
        fields = {
            'Teams Channel ID': channel_id,
            'Channel Url': channel_url,
        }
        
        print(f'[setup] Patching Airtable: {fields}')
        
        response = httpx.patch(
            f"{_url(PROJECTS_TABLE)}/{record_id}",
            headers=_headers(),
            json={'fields': fields},
            timeout=10.0
        )
        response.raise_for_status()
        
        print(f'[setup] Airtable updated successfully')
        
    except Exception as e:
        print(f'[setup] Airtable update failed: {e}')
        return {
            'success': False, 
            'error': f'Channel created but Airtable update failed: {e}',
            'channelId': channel_id,
            'channelUrl': channel_url,
        }
    
    return {
        'success': True,
        'jobNumber': job_number,
        'channelId': channel_id,
        'channelUrl': channel_url,
    }
