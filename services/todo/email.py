"""
TO DO Email Builder
Generates HTML email matching Dot's standard email style.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

# ===================
# CONFIG
# ===================

BRAND_RED = '#ED1C24'
DARK_GREY = '#333'
NZ_TZ = ZoneInfo('Pacific/Auckland')
LOGO_URL = "https://raw.githubusercontent.com/MGhunch/dot-hub/main/images/ai2-logo.png"
ASK_DOT_HEADER = "https://raw.githubusercontent.com/MGhunch/dot-hub/main/images/Askdot-header.png"


# ===================
# HELPERS
# ===================

def _get_day_name():
    """Get today's day name: 'Thursday'"""
    return datetime.now(NZ_TZ).strftime('%A')


def _section_header(text):
    """Build section header (TODAY, TOMORROW) - dark grey."""
    return f'<div style="font-size: 20px; font-weight: 600; color: {DARK_GREY}; margin: 28px 0 16px 0;">{text}</div>'


def _section_subtitle(text):
    """Build section subtitle (MEETINGS, JOBS DUE) - red."""
    return f'<div style="font-size: 13px; font-weight: 600; color: {BRAND_RED}; text-transform: uppercase; letter-spacing: 0.5px; margin: 20px 0 10px 0;">{text}</div>'


def _meeting_card(meeting):
    """Build HTML for a meeting card."""
    start = meeting.get('startTime', '')
    end = meeting.get('endTime', '')
    time_str = f"{start} – {end}" if end else start
    
    return f'''<div style="background: #f9f9f9; border-radius: 12px; padding: 16px 18px; margin-bottom: 10px;">
  <div style="margin-bottom: 8px;">
    <span style="font-size: 15px; font-weight: 600; color: {DARK_GREY};">{time_str}</span>
    <span style="font-size: 11px; font-weight: 600; color: #666; background: #eee; padding: 4px 10px; border-radius: 999px; text-transform: uppercase; letter-spacing: 0.5px; margin-left: 10px;">{meeting.get('whose', 'Michael')}</span>
  </div>
  <div style="font-weight: 600; font-size: 17px; color: #1a1a1a; margin-bottom: 4px;">{meeting.get('title', '')}</div>
  <div style="font-size: 15px; color: #666;">📍 {meeting.get('location', 'TBC')}</div>
</div>'''


def _job_card(job, hub_link):
    """Build HTML for a job card - Option C layout."""
    status = job.get('status', '')
    status_style = f'color: {BRAND_RED}; background: rgba(237, 28, 36, 0.1);' if status == 'Overdue' else 'color: #666; background: #eee;'
    
    # Teams button - only if channel URL exists
    teams_button = ''
    if job.get('channelUrl'):
        teams_button = f'<a href="{job["channelUrl"]}" style="font-size: 13px; font-weight: 600; text-decoration: none; color: #666; margin-left: 20px;">› TEAMS</a>'
    
    description = job.get('description', '')
    if len(description) > 100:
        description = description[:97] + '...'
    
    job_number = job.get('jobNumber', '')
    job_name = job.get('jobName', '')
    
    return f'''<div style="background: #f9f9f9; border-radius: 12px; padding: 16px 18px; margin-bottom: 10px;">
  <div style="margin-bottom: 8px;">
    <span style="font-size: 15px; font-weight: 600; color: #1a1a1a;">{job_number}</span>
    <span style="color: #ccc; margin: 0 8px;">·</span>
    <span style="font-size: 15px; font-weight: 600; color: #1a1a1a;">{job_name}</span>
    <span style="font-size: 11px; font-weight: 600; {status_style} padding: 4px 10px; border-radius: 999px; text-transform: uppercase; letter-spacing: 0.3px; float: right;">{status}</span>
  </div>
  <div style="font-size: 15px; color: #666; line-height: 1.4; margin-bottom: 12px;">{description}</div>
  <div>
    <a href="{hub_link}" style="font-size: 13px; font-weight: 600; text-decoration: none; color: #666;">› UPDATE</a>{teams_button}
  </div>
</div>'''


def _week_item(job, hub_link):
    """Build HTML for a 'coming up' list item."""
    return f'''<div style="padding: 10px 0; border-bottom: 1px solid #eee;">
  <a href="{hub_link}" style="font-size: 15px; font-weight: 600; text-decoration: none; color: #1a1a1a;">{job.get('jobNumber', '')}</a>
  <span style="font-size: 15px; color: #666;"> · {job.get('jobName', '')}</span>
  <span style="font-size: 13px; color: #999; float: right;">{job.get('status', '')}</span>
</div>'''


def _empty_state(text):
    """Build empty state message - left aligned."""
    return f'<div style="background: #f9f9f9; border-radius: 12px; padding: 16px 18px; color: #999; font-size: 15px;">{text}</div>'


def _header():
    """Build Ask Dot header with red underline."""
    return f'''<div style="padding-bottom: 16px; border-bottom: 3px solid {BRAND_RED}; margin-bottom: 24px;">
  <img src="{ASK_DOT_HEADER}" alt="Ask Dot" height="32" style="display: block;">
</div>'''


def _footer():
    """Build standard Dot footer."""
    return f'''<table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-top: 32px; border-top: 1px solid #eee; padding-top: 16px;">
  <tr>
    <td style="vertical-align: middle; padding-right: 12px;" width="60">
      <img src="{LOGO_URL}" alt="hai2" width="56" height="28" style="display: block;">
    </td>
    <td style="vertical-align: middle; font-size: 12px; color: #999;">
      Dot is a robot, but there's humans in the loop.
    </td>
  </tr>
</table>'''


# ===================
# MAIN BUILDER
# ===================

def build_todo_email(jobs, meetings, job_links, next_day_label='Tomorrow', first_name='Michael', week_label='Coming up this week'):
    """
    Build the complete TO DO email HTML.
    
    Args:
        jobs: {'today': [...], 'tomorrow': [...], 'week': [...]}
        meetings: {'today': [...], 'tomorrow': [...]}
        job_links: dict mapping job_number -> hub_link
        next_day_label: 'Tomorrow' or 'Monday'
        first_name: recipient's first name
        week_label: 'Coming up this week' or 'Coming up next week'
    
    Returns:
        Complete HTML string
    """
    
    # === INTRO ===
    intro_html = f'''<p style="margin: 0 0 6px 0; font-size: 16px;">Hey {first_name},</p>
<p style="margin: 0; font-size: 16px; color: #666;">Here's what's what and what's hot.</p>'''
    
    # === TODAY SECTION ===
    today_html = _section_header('Today')
    
    # Today's meetings
    today_html += _section_subtitle('Meetings')
    if meetings.get('today'):
        for meeting in meetings['today']:
            today_html += _meeting_card(meeting)
    else:
        today_html += _empty_state('No meetings today')
    
    # Today's jobs
    today_html += _section_subtitle('Jobs due')
    if jobs.get('today'):
        for job in jobs['today']:
            hub_link = job_links.get(job.get('jobNumber'), '#')
            today_html += _job_card(job, hub_link)
    else:
        today_html += _empty_state('No jobs due today')
    
    # === TOMORROW/MONDAY SECTION ===
    tomorrow_html = _section_header(next_day_label)
    
    # Tomorrow's meetings
    tomorrow_html += _section_subtitle('Meetings')
    if meetings.get('tomorrow'):
        for meeting in meetings['tomorrow']:
            tomorrow_html += _meeting_card(meeting)
    else:
        tomorrow_html += _empty_state(f'No meetings {next_day_label.lower()}')
    
    # Tomorrow's jobs
    tomorrow_html += _section_subtitle('Jobs due')
    if jobs.get('tomorrow'):
        for job in jobs['tomorrow']:
            hub_link = job_links.get(job.get('jobNumber'), '#')
            tomorrow_html += _job_card(job, hub_link)
    else:
        tomorrow_html += _empty_state(f'No jobs due {next_day_label.lower()}')
    
    # === COMING UP ===
    week_html = ''
    if jobs.get('week'):
        week_html = _section_header(week_label)
        for job in jobs['week']:
            hub_link = job_links.get(job.get('jobNumber'), '#')
            week_html += _week_item(job, hub_link)
    
    # === COMPLETE EMAIL ===
    email_html = f'''<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 15px; line-height: 1.6; color: #333; margin: 0; padding: 20px; background: #f5f5f5;">

<div style="max-width: 600px; margin: 0 auto; background: white; padding: 24px; border-radius: 8px;">

{_header()}
{intro_html}
{today_html}
{tomorrow_html}
{week_html}
{_footer()}

</div>

</body>
</html>'''
    
    return email_html


def get_subject_line():
    """Get the email subject line with today's day name."""
    return f"Daily To Do List: {_get_day_name()}"
