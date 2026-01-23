"""
Dot Workers - Connect
Communication layer for workers: Teams posts and confirmation emails.

Workers do the work, then call these functions to communicate results.
Calls PA Postman and PA Teamsbot directly.
"""

import os
import httpx

# ===================
# CONFIG
# ===================

PA_POSTMAN_URL = os.environ.get('PA_POSTMAN_URL', '')
PA_TEAMSBOT_URL = os.environ.get('PA_TEAMSBOT_URL', '')

TIMEOUT = 30.0

# Logo for email footer
LOGO_URL = "https://raw.githubusercontent.com/MGhunch/dot-hub/main/images/ai2-logo.png"


# ===================
# HELPERS
# ===================

def _get_first_name(sender_name):
    """Extract first name from sender name, fallback to 'there'"""
    if not sender_name:
        return "there"
    first = sender_name.split()[0].strip('"\'[]()') if sender_name else "there"
    return first if first else "there"


def _email_wrapper(content):
    """Wrap email content with consistent styling and footer"""
    return f"""<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #333;">
{content}

<table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-top: 32px; border-top: 1px solid #eee; padding-top: 16px;">
  <tr>
    <td style="vertical-align: middle; padding-right: 12px;" width="60">
      <img src="{LOGO_URL}" alt="hai2" width="56" height="28" style="display: block;">
    </td>
    <td style="vertical-align: middle; font-size: 12px; color: #999;">
      Dot is a robot, but there's humans in the loop.
    </td>
  </tr>
</table>
</div>"""


def _success_box(title, subtitle):
    """Green success detail box with tick"""
    return f"""<table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom: 20px;">
  <tr>
    <td style="background: #f0fdf4; border-radius: 8px; padding: 16px; border-left: 4px solid #22c55e;">
      <table cellpadding="0" cellspacing="0" border="0" width="100%">
        <tr>
          <td width="28" style="vertical-align: top; padding-right: 12px;">
            <div style="width: 24px; height: 24px; background: #22c55e; border-radius: 50%; text-align: center; line-height: 24px;">
              <span style="color: white; font-size: 14px;">✓</span>
            </div>
          </td>
          <td style="vertical-align: top;">
            <div style="font-weight: 600; color: #333; margin-bottom: 2px;">{title}</div>
            <div style="font-size: 13px; color: #666;">{subtitle}</div>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>"""


# ===================
# TEAMS POSTING
# ===================

def post_to_teams(team_id, channel_id, subject, body, job_number=None):
    """
    Post a message to a Teams channel via PA Teamsbot.
    
    Args:
        team_id: The Teams team ID
        channel_id: The Teams channel ID
        subject: Message subject line
        body: Message body (the update summary + context)
        job_number: Optional job number for logging
    
    Returns:
        dict with success status
    """
    if not team_id or not channel_id:
        print(f"[connect] Teams post skipped - missing IDs (team: {team_id}, channel: {channel_id})")
        return {
            'success': False,
            'error': 'Missing teamId or channelId',
            'skipped': True
        }
    
    teams_payload = {
        'teamId': team_id,
        'channelId': channel_id,
        'subject': subject or '',
        'message': body,
        'jobNumber': job_number or ''
    }
    
    print(f"[connect] Posting to Teams: {subject}")
    
    if not PA_TEAMSBOT_URL:
        print(f"[connect] PA_TEAMSBOT_URL not configured")
        return {
            'success': False,
            'error': 'PA_TEAMSBOT_URL not configured',
            'would_send': teams_payload
        }
    
    try:
        response = httpx.post(
            PA_TEAMSBOT_URL,
            json=teams_payload,
            timeout=TIMEOUT,
            headers={'Content-Type': 'application/json'}
        )
        
        success = response.status_code in [200, 202]
        print(f"[connect] Teams post: {success} (status {response.status_code})")
        
        return {
            'success': success,
            'response_code': response.status_code
        }
        
    except Exception as e:
        print(f"[connect] Error posting to Teams: {e}")
        return {
            'success': False,
            'error': str(e)
        }


# ===================
# CONFIRMATION EMAIL
# ===================

def send_confirmation(to_email, route, sender_name=None, job_number=None, 
                      job_name=None, subject_line=None, original_email=None):
    """
    Send a confirmation email after successful worker action.
    
    Args:
        to_email: Recipient email
        route: What was done ('update', 'file', etc.)
        sender_name: For greeting
        job_number: e.g., 'LAB 055'
        job_name: e.g., 'Campaign refresh'
        subject_line: Original email subject (for Re:)
        original_email: Dict for email trail:
            {
                'senderName': 'Michael',
                'senderEmail': 'michael@hunch.co.nz',
                'subject': 'Original subject',
                'receivedDateTime': '2026-01-24T08:00:00Z',
                'content': 'Original email body'
            }
    
    Returns:
        dict with success status
    """
    first_name = _get_first_name(sender_name)
    
    # Friendly text based on route
    friendly_text = {
        'update': 'Job updated',
        'file': 'Files filed',
        'triage': 'Job triaged',
    }.get(route, 'Request completed')
    
    # Build title line
    if job_number and job_name:
        box_title = f"{job_number} | {job_name}"
    elif job_number:
        box_title = job_number
    else:
        box_title = "Done"
    
    # Build subtitle
    subtitle = {
        'update': 'Status updated',
        'file': 'Filed to job folder',
        'triage': 'New job created',
    }.get(route, 'Completed')
    
    content = f"""<p style="margin: 0 0 20px 0;">Hey {first_name},</p>
<p style="margin: 0 0 20px 0;">All sorted. {friendly_text}.</p>

{_success_box(box_title, subtitle)}

<p style="margin: 0;">Dot</p>"""
    
    body_html = _email_wrapper(content)
    subject = f"Re: {subject_line}" if subject_line else "Dot - Done"
    
    # Build payload for PA Postman
    postman_payload = {
        'to': to_email,
        'subject': subject,
        'body': body_html
    }
    
    # Include original email for trail if provided
    if original_email:
        postman_payload['replyTo'] = {
            'from': original_email.get('senderName', ''),
            'fromEmail': original_email.get('senderEmail', ''),
            'sent': original_email.get('receivedDateTime', ''),
            'subject': original_email.get('subject', ''),
            'body': original_email.get('content', '')
        }
    
    print(f"[connect] Sending confirmation: {friendly_text} -> {to_email}")
    
    if not PA_POSTMAN_URL:
        print(f"[connect] PA_POSTMAN_URL not configured")
        return {
            'success': False,
            'error': 'PA_POSTMAN_URL not configured',
            'would_send': postman_payload
        }
    
    try:
        response = httpx.post(
            PA_POSTMAN_URL,
            json=postman_payload,
            timeout=TIMEOUT,
            headers={'Content-Type': 'application/json'}
        )
        
        success = response.status_code in [200, 202]
        print(f"[connect] Email sent: {success} (status {response.status_code})")
        
        return {
            'success': success,
            'response_code': response.status_code
        }
        
    except Exception as e:
        print(f"[connect] Error sending email: {e}")
        return {
            'success': False,
            'error': str(e)
        }


# ===================
# FAILURE EMAIL
# ===================

def send_failure(to_email, route, error_message, sender_name=None, 
                 job_number=None, subject_line=None, original_email=None):
    """
    Send a failure notification email when something goes wrong.
    
    Args:
        to_email: Recipient email
        route: What failed ('update', 'file', etc.)
        error_message: What went wrong
        sender_name: For greeting
        job_number: e.g., 'LAB 055'
        subject_line: Original email subject
        original_email: Dict for email trail
    
    Returns:
        dict with success status
    """
    first_name = _get_first_name(sender_name)
    
    # Build title line
    box_title = job_number if job_number else "Error"
    
    # Build subtitle based on route
    box_subtitle = {
        'update': "Couldn't update job",
        'file': "Couldn't file attachments",
        'triage': "Couldn't create job",
    }.get(route, "Something went wrong")
    
    failure_box = f"""<table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom: 20px;">
  <tr>
    <td style="background: #fef2f2; border-radius: 8px; padding: 16px; border-left: 4px solid #ef4444;">
      <table cellpadding="0" cellspacing="0" border="0" width="100%">
        <tr>
          <td width="28" style="vertical-align: top; padding-right: 12px;">
            <div style="width: 24px; height: 24px; background: #ef4444; border-radius: 50%; text-align: center; line-height: 24px;">
              <span style="color: white; font-size: 14px;">✕</span>
            </div>
          </td>
          <td style="vertical-align: top;">
            <div style="font-weight: 600; color: #333; margin-bottom: 2px;">{box_title}</div>
            <div style="font-size: 13px; color: #666;">{box_subtitle}</div>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>"""
    
    content = f"""<p style="margin: 0 0 20px 0;">Hey {first_name},</p>
<p style="margin: 0 0 20px 0;">Sorry, I got in a muddle over that one.</p>

{failure_box}

<p style="margin: 0 0 8px 0; font-size: 13px; color: #666;">Here's what I told myself:</p>
<pre style="background: #f5f5f5; padding: 12px; border-radius: 6px; font-size: 12px; overflow-x: auto; color: #666; margin: 0 0 24px 0;">{error_message}</pre>

<p style="margin: 0;">Dot</p>"""
    
    body_html = _email_wrapper(content)
    subject = f"Did not compute: {subject_line}" if subject_line else "Did not compute"
    
    # Build payload for PA Postman
    postman_payload = {
        'to': to_email,
        'subject': subject,
        'body': body_html
    }
    
    # Include original email for trail if provided
    if original_email:
        postman_payload['replyTo'] = {
            'from': original_email.get('senderName', ''),
            'fromEmail': original_email.get('senderEmail', ''),
            'sent': original_email.get('receivedDateTime', ''),
            'subject': original_email.get('subject', ''),
            'body': original_email.get('content', '')
        }
    
    print(f"[connect] Sending failure: {route} -> {to_email}")
    
    if not PA_POSTMAN_URL:
        print(f"[connect] PA_POSTMAN_URL not configured")
        return {
            'success': False,
            'error': 'PA_POSTMAN_URL not configured',
            'would_send': postman_payload
        }
    
    try:
        response = httpx.post(
            PA_POSTMAN_URL,
            json=postman_payload,
            timeout=TIMEOUT,
            headers={'Content-Type': 'application/json'}
        )
        
        success = response.status_code in [200, 202]
        print(f"[connect] Email sent: {success} (status {response.status_code})")
        
        return {
            'success': success,
            'response_code': response.status_code
        }
        
    except Exception as e:
        print(f"[connect] Error sending email: {e}")
        return {
            'success': False,
            'error': str(e)
        }
