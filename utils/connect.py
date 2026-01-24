"""
Dot Workers - Connect
Shared communication for all workers: Teams + emails.
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

LOGO_URL = "https://raw.githubusercontent.com/MGhunch/dot-hub/main/images/ai2-logo.png"


# ===================
# HELPERS
# ===================

def _get_first_name(sender_name):
    if not sender_name:
        return "there"
    first = sender_name.split()[0].strip('"\'[]()') if sender_name else "there"
    return first if first else "there"


def _email_wrapper(content):
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


def _failure_box(title, subtitle):
    return f"""<table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom: 20px;">
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
            <div style="font-weight: 600; color: #333; margin-bottom: 2px;">{title}</div>
            <div style="font-size: 13px; color: #666;">{subtitle}</div>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>"""


# ===================
# TEAMS
# ===================

def post_to_teams(team_id, channel_id, subject, body, job_number=None):
    """Post to Teams channel via PA Teamsbot"""
    if not team_id or not channel_id:
        print(f"[connect] Teams skipped - missing IDs")
        return {'success': False, 'error': 'Missing teamId or channelId', 'skipped': True}
    
    payload = {
        'teamId': team_id,
        'channelId': channel_id,
        'subject': subject or '',
        'message': body,
        'jobNumber': job_number or ''
    }
    
    print(f"[connect] Posting to Teams: {subject}")
    
    if not PA_TEAMSBOT_URL:
        print(f"[connect] PA_TEAMSBOT_URL not configured")
        return {'success': False, 'error': 'PA_TEAMSBOT_URL not configured'}
    
    try:
        response = httpx.post(PA_TEAMSBOT_URL, json=payload, timeout=TIMEOUT)
        success = response.status_code in [200, 202]
        print(f"[connect] Teams: {success} ({response.status_code})")
        return {'success': success, 'response_code': response.status_code}
    except Exception as e:
        print(f"[connect] Teams error: {e}")
        return {'success': False, 'error': str(e)}


# ===================
# CONFIRMATION EMAIL
# ===================

def send_confirmation(to_email, route, sender_name=None, job_number=None, 
                      job_name=None, subject_line=None, original_email=None):
    """Send confirmation email after successful action"""
    first_name = _get_first_name(sender_name)
    
    friendly_text = {
        'update': 'Job updated',
        'file': 'Files filed',
        'triage': 'Job triaged',
        'newjob': 'New job created',
    }.get(route, 'Request completed')
    
    if job_number and job_name:
        box_title = f"{job_number} | {job_name}"
    elif job_number:
        box_title = job_number
    else:
        box_title = "Done"
    
    subtitle = {
        'update': 'Status updated',
        'file': 'Filed to job folder',
        'triage': 'New job created',
        'newjob': 'Added to pipeline',
    }.get(route, 'Completed')
    
    content = f"""<p style="margin: 0 0 20px 0;">Hey {first_name},</p>
<p style="margin: 0 0 20px 0;">All sorted. {friendly_text}.</p>

{_success_box(box_title, subtitle)}

<p style="margin: 0;">Dot</p>"""
    
    body_html = _email_wrapper(content)
    subject = f"Re: {subject_line}" if subject_line else "Dot - Done"
    
    payload = {
        'to': to_email,
        'subject': subject,
        'body': body_html
    }
    
    if original_email:
        payload['replyTo'] = {
            'from': original_email.get('senderName', ''),
            'fromEmail': original_email.get('senderEmail', ''),
            'sent': original_email.get('receivedDateTime', ''),
            'subject': original_email.get('subject', ''),
            'body': original_email.get('content', '')
        }
    
    print(f"[connect] Confirmation: {friendly_text} -> {to_email}")
    
    if not PA_POSTMAN_URL:
        print(f"[connect] PA_POSTMAN_URL not configured")
        return {'success': False, 'error': 'PA_POSTMAN_URL not configured'}
    
    try:
        response = httpx.post(PA_POSTMAN_URL, json=payload, timeout=TIMEOUT)
        success = response.status_code in [200, 202]
        print(f"[connect] Email: {success} ({response.status_code})")
        return {'success': success, 'response_code': response.status_code}
    except Exception as e:
        print(f"[connect] Email error: {e}")
        return {'success': False, 'error': str(e)}


# ===================
# FAILURE EMAIL
# ===================

def send_failure(to_email, route, error_message, sender_name=None, 
                 job_number=None, subject_line=None, original_email=None):
    """Send failure email when something goes wrong"""
    first_name = _get_first_name(sender_name)
    
    box_title = job_number if job_number else "Error"
    box_subtitle = {
        'update': "Couldn't update job",
        'file': "Couldn't file attachments",
        'triage': "Couldn't create job",
        'newjob': "Couldn't create job",
    }.get(route, "Something went wrong")
    
    content = f"""<p style="margin: 0 0 20px 0;">Hey {first_name},</p>
<p style="margin: 0 0 20px 0;">Sorry, I got in a muddle over that one.</p>

{_failure_box(box_title, box_subtitle)}

<p style="margin: 0 0 8px 0; font-size: 13px; color: #666;">Here's what I told myself:</p>
<pre style="background: #f5f5f5; padding: 12px; border-radius: 6px; font-size: 12px; overflow-x: auto; color: #666; margin: 0 0 24px 0;">{error_message}</pre>

<p style="margin: 0;">Dot</p>"""
    
    body_html = _email_wrapper(content)
    subject = f"Did not compute: {subject_line}" if subject_line else "Did not compute"
    
    payload = {
        'to': to_email,
        'subject': subject,
        'body': body_html
    }
    
    if original_email:
        payload['replyTo'] = {
            'from': original_email.get('senderName', ''),
            'fromEmail': original_email.get('senderEmail', ''),
            'sent': original_email.get('receivedDateTime', ''),
            'subject': original_email.get('subject', ''),
            'body': original_email.get('content', '')
        }
    
    print(f"[connect] Failure: {route} -> {to_email}")
    
    if not PA_POSTMAN_URL:
        print(f"[connect] PA_POSTMAN_URL not configured")
        return {'success': False, 'error': 'PA_POSTMAN_URL not configured'}
    
    try:
        response = httpx.post(PA_POSTMAN_URL, json=payload, timeout=TIMEOUT)
        success = response.status_code in [200, 202]
        print(f"[connect] Email: {success} ({response.status_code})")
        return {'success': success, 'response_code': response.status_code}
    except Exception as e:
        print(f"[connect] Email error: {e}")
        return {'success': False, 'error': str(e)}
