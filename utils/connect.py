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
              <span style="color: white; font-size: 14px;">✗</span>
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


def _checklist_item(success, text):
    """Build a single checklist item - tick or cross"""
    if success:
        return f'<div style="margin-bottom: 8px; color: #333;"><span style="color: #22c55e; margin-right: 8px;">✓</span>{text}</div>'
    else:
        return f'<div style="margin-bottom: 8px; color: #999;"><span style="color: #ef4444; margin-right: 8px;">✗</span>{text}</div>'


def _files_button(url):
    """Build red pill button for files link"""
    return f'<a href="{url}" style="display: inline-block; border: 2px solid #ED1C24; color: #ED1C24; text-decoration: none; padding: 8px 20px; border-radius: 50px; font-size: 14px; font-weight: 500; margin-top: 8px;">› Here\'s the files</a>'


def _channel_button(url):
    """Build red pill button for Teams channel link"""
    return f'<a href="{url}" style="display: inline-block; border: 2px solid #ED1C24; color: #ED1C24; text-decoration: none; padding: 8px 20px; border-radius: 50px; font-size: 14px; font-weight: 500; margin-top: 8px;">› Open in Teams</a>'


def _build_checklist(results, files_url=None):
    """
    Build checklist HTML from results dict.
    
    Returns tuple: (checklist_html, has_any_failure, files_button_html)
    """
    items = []
    has_failure = False
    
    # Files
    file_result = results.get('file')
    if file_result:
        if file_result.get('success') and file_result.get('filed'):
            count = file_result.get('count', 0)
            if count > 0:
                items.append(_checklist_item(True, f"{count} file{'s' if count != 1 else ''} filed"))
        elif file_result.get('error'):
            has_failure = True
            if 'No job bag' in file_result.get('error', ''):
                items.append(_checklist_item(False, "Files not filed (no job bag)"))
            else:
                items.append(_checklist_item(False, "Files not filed"))
    
    # Airtable
    airtable_result = results.get('airtable')
    if airtable_result:
        if airtable_result.get('success'):
            items.append(_checklist_item(True, "Job updated"))
        else:
            has_failure = True
            items.append(_checklist_item(False, "Job not updated"))
    
    # Teams
    teams_result = results.get('teams')
    if teams_result:
        if teams_result.get('success'):
            items.append(_checklist_item(True, "Posted to Teams"))
        elif teams_result.get('skipped'):
            has_failure = True
            items.append(_checklist_item(False, "Teams skipped (no channel)"))
        else:
            has_failure = True
            items.append(_checklist_item(False, "Teams post failed"))
    
    checklist_html = ''
    if items:
        checklist_html = f'<div style="margin: 16px 0;">{"".join(items)}</div>'
    
    # Files button (only if files were successfully filed)
    button_html = ''
    if files_url and file_result and file_result.get('success') and file_result.get('filed'):
        button_html = _files_button(files_url)
    
    return checklist_html, has_failure, button_html


def _build_setup_checklist(results):
    """
    Build checklist HTML for setup results.
    
    Returns tuple: (checklist_html, has_any_failure)
    """
    items = []
    has_failure = False
    
    # Project
    project_result = results.get('project')
    if project_result:
        if project_result.get('success'):
            items.append(_checklist_item(True, "Job created"))
        else:
            has_failure = True
            items.append(_checklist_item(False, "Job not created"))
    
    # Tracker
    tracker_result = results.get('tracker')
    if tracker_result:
        if tracker_result.get('success'):
            items.append(_checklist_item(True, "Added to Tracker"))
        else:
            has_failure = True
            items.append(_checklist_item(False, "Tracker not updated"))
    
    # Channel
    channel_result = results.get('channel')
    if channel_result:
        if channel_result.get('success'):
            items.append(_checklist_item(True, "Teams channel created"))
        elif channel_result.get('skipped'):
            has_failure = True
            items.append(_checklist_item(False, "Teams channel skipped (no Team ID)"))
        else:
            has_failure = True
            items.append(_checklist_item(False, "Teams channel not created"))
    
    # Teams post
    teams_post_result = results.get('teams_post')
    if teams_post_result:
        if teams_post_result.get('success'):
            items.append(_checklist_item(True, "Brief posted to Teams"))
        elif teams_post_result.get('skipped'):
            pass  # Don't show - redundant with channel skipped
        else:
            has_failure = True
            items.append(_checklist_item(False, "Brief not posted"))
    
    checklist_html = ''
    if items:
        checklist_html = f'<div style="margin: 16px 0;">{"".join(items)}</div>'
    
    return checklist_html, has_failure


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
                      job_name=None, subject_line=None, original_email=None,
                      files_url=None, channel_url=None, results=None):
    """
    Send confirmation email after successful action.
    
    If results dict is provided, shows a checklist of what happened.
    Includes buttons for Teams channel and files if URLs provided.
    Includes email trail at bottom after signature.
    """
    first_name = _get_first_name(sender_name)
    
    # Build title
    if job_number and job_name:
        box_title = f"{job_number} | {job_name}"
    elif job_number:
        box_title = job_number
    else:
        box_title = "Done"
    
    # Build checklist if we have results
    if results:
        checklist_html, has_failure, _ = _build_checklist(results, files_url)
        
        # Dynamic intro based on success/failure
        if has_failure:
            intro = "Mostly sorted, here's what I had."
        else:
            intro = "All sorted, here's what's done."
    else:
        checklist_html = ''
        has_failure = False
        intro = "All sorted."
    
    # Build buttons (Teams + Files)
    buttons = []
    if channel_url:
        buttons.append(f'<a href="{channel_url}" style="display: inline-block; border: 2px solid #ED1C24; color: #ED1C24; text-decoration: none; padding: 8px 20px; border-radius: 50px; font-size: 14px; font-weight: 500;">› Open in Teams</a>')
    if files_url:
        buttons.append(f'<a href="{files_url}" style="display: inline-block; border: 2px solid #ED1C24; color: #ED1C24; text-decoration: none; padding: 8px 20px; border-radius: 50px; font-size: 14px; font-weight: 500;">› See the files</a>')
    buttons_html = f'<div style="margin-top: 12px;">{" &nbsp; ".join(buttons)}</div>' if buttons else ''
    
    # Build email trail
    trail_html = ''
    if original_email and original_email.get('content'):
        trail_html = f'''<div style="background: #f5f5f5; border-radius: 8px; padding: 12px; font-size: 13px; color: #666;">
  <div style="font-weight: 600; margin-bottom: 8px; color: #333;">Original request</div>
  {original_email['content'][:500]}{'...' if len(original_email.get('content', '')) > 500 else ''}
</div>'''
    
    # Build content
    content = f"""<p style="margin: 0 0 20px 0;">Hey {first_name},</p>
<p style="margin: 0 0 12px 0;">{intro}</p>

<div style="background: #f9f9f9; border-radius: 0 8px 8px 0; padding: 16px; margin-bottom: 20px; border-left: 4px solid #ED1C24;">
  <div style="font-weight: 600; color: #333; margin-bottom: 12px;">{box_title}</div>
  {checklist_html}
  {buttons_html}
</div>

<p style="margin: 0 0 20px 0;">Dot</p>
{trail_html}"""
    
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
    
    print(f"[connect] Confirmation: {route} -> {to_email}")
    
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
# SETUP CONFIRMATION EMAIL
# ===================

def send_setup_confirmation(to_email, sender_name=None, job_number=None,
                            job_name=None, channel_url=None, files_url=None,
                            subject_line=None, original_email=None, brief=None, results=None):
    """
    Send confirmation email after new job setup.
    
    Shows what was created and provides links to Teams channel and files.
    Includes brief summary or original email trail.
    """
    first_name = _get_first_name(sender_name)
    
    # Build title
    box_title = f"{job_number} | {job_name}" if job_number and job_name else job_number or "New Job"
    
    # Build checklist
    checklist_html, has_failure = _build_setup_checklist(results) if results else ('', False)
    
    # Dynamic intro
    if has_failure:
        intro = "Mostly set up - a couple of things didn't quite work."
    else:
        intro = "All set up and ready to go."
    
    # Build buttons (Teams + Files)
    buttons = []
    if channel_url:
        buttons.append(f'<a href="{channel_url}" style="display: inline-block; border: 2px solid #ED1C24; color: #ED1C24; text-decoration: none; padding: 8px 20px; border-radius: 50px; font-size: 14px; font-weight: 500;">› Open in Teams</a>')
    if files_url:
        buttons.append(f'<a href="{files_url}" style="display: inline-block; border: 2px solid #ED1C24; color: #ED1C24; text-decoration: none; padding: 8px 20px; border-radius: 50px; font-size: 14px; font-weight: 500;">› See the files</a>')
    buttons_html = f'<div style="margin-top: 12px;">{" &nbsp; ".join(buttons)}</div>' if buttons else ''
    
    # Build brief/request summary
    trail_html = ''
    if brief:
        # Hub form submission - show brief details
        brief_parts = []
        if brief.get('theJob'):
            brief_parts.append(f"<b>What's the job?</b> {brief['theJob']}")
        if brief.get('owner'):
            brief_parts.append(f"<b>Owner:</b> {brief['owner']}")
        if brief.get('costs'):
            brief_parts.append(f"<b>Tracker:</b> {brief['costs']}")
        if brief.get('when'):
            brief_parts.append(f"<b>Live:</b> {brief['when']}")
        if brief_parts:
            trail_html = f'''<div style="background: #f5f5f5; border-radius: 8px; padding: 12px; margin-top: 16px; font-size: 13px; color: #666;">
  <div style="font-weight: 600; margin-bottom: 8px; color: #333;">Brief</div>
  {'<br>'.join(brief_parts)}
</div>'''
    elif original_email and original_email.get('content'):
        # Email submission - show original email
        trail_html = f'''<div style="background: #f5f5f5; border-radius: 8px; padding: 12px; margin-top: 16px; font-size: 13px; color: #666;">
  <div style="font-weight: 600; margin-bottom: 8px; color: #333;">Original request</div>
  {original_email['content'][:500]}{'...' if len(original_email.get('content', '')) > 500 else ''}
</div>'''
    
    content = f"""<p style="margin: 0 0 20px 0;">Hey {first_name},</p>
<p style="margin: 0 0 12px 0;">{intro}</p>

<div style="background: #f9f9f9; border-radius: 0 8px 8px 0; padding: 16px; margin-bottom: 20px; border-left: 4px solid #ED1C24;">
  <div style="font-weight: 600; color: #333; margin-bottom: 12px;">{box_title}</div>
  {checklist_html}
  {buttons_html}
</div>

<p style="margin: 0 0 20px 0;">Dot</p>
{trail_html}"""
    
    body_html = _email_wrapper(content)
    subject = f"Set up: {job_number} - {job_name}" if job_number else f"Re: {subject_line}"
    
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
    
    print(f"[connect] Setup confirmation -> {to_email}")
    
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
        'setup': "Couldn't set up job",
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
