"""
TO DO Email Builder
Generates HTML email matching the TO DO mockup design.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

# ===================
# CONFIG
# ===================

BRAND_RED = '#ED1C24'
NZ_TZ = ZoneInfo('Pacific/Auckland')


# ===================
# HELPERS
# ===================

def _get_today_formatted():
    """Get today's date formatted: 'Wednesday, 5 February 2026'"""
    now = datetime.now(NZ_TZ)
    return now.strftime('%A, %-d %B %Y')


def _meeting_card(meeting):
    """Build HTML for a meeting card."""
    start = meeting.get('startTime', '')
    end = meeting.get('endTime', '')
    time_str = f"{start} – {end}" if end else start
    
    return f'''<div style="background: white; border-radius: 16px; padding: 16px 18px; margin-bottom: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
    <div style="font-size: 13px; font-weight: 600; color: {BRAND_RED};">{time_str}</div>
    <div style="font-size: 10px; font-weight: 600; color: #666; background: #f5f5f5; padding: 4px 10px; border-radius: 999px; text-transform: uppercase; letter-spacing: 0.5px;">{meeting.get('whose', 'Michael')}</div>
  </div>
  <div style="font-weight: 600; font-size: 15px; color: #1a1a1a; margin-bottom: 4px;">{meeting.get('title', '')}</div>
  <div style="font-size: 13px; color: #666;">📍 {meeting.get('location', 'TBC')}</div>
</div>'''


def _job_card(job, hub_link):
    """Build HTML for a job card with UPDATE and TEAMS buttons."""
    status = job.get('status', '')
    status_class = 'color: #ED1C24; background: rgba(237, 28, 36, 0.08);' if status == 'Overdue' else 'color: #666; background: #f5f5f5;'
    
    # UPDATE button SVG
    update_svg = '''<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 14px; height: 14px; vertical-align: middle;">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
    </svg>'''
    
    # TEAMS button SVG
    teams_svg = '''<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 14px; height: 14px; vertical-align: middle;">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
    </svg>'''
    
    # Teams button - only if channel URL exists
    teams_button = ''
    if job.get('channelUrl'):
        teams_button = f'''<a href="{job['channelUrl']}" style="display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600; text-decoration: none; padding: 8px 14px; border-radius: 999px; background: #f5f5f5; color: #666;">
        {teams_svg} TEAMS
      </a>'''
    
    description = job.get('description', '')
    # Truncate long descriptions
    if len(description) > 80:
        description = description[:77] + '...'
    
    return f'''<div style="background: white; border-radius: 16px; padding: 16px 18px; margin-bottom: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
    <div style="font-size: 11px; font-weight: 600; color: {BRAND_RED}; background: rgba(237, 28, 36, 0.08); padding: 4px 10px; border-radius: 999px; letter-spacing: 0.5px;">{job.get('jobNumber', '')}</div>
    <div style="font-size: 10px; font-weight: 600; {status_class} padding: 4px 10px; border-radius: 999px; text-transform: uppercase;">{status}</div>
  </div>
  <div style="font-weight: 600; font-size: 15px; color: #1a1a1a; margin-bottom: 4px;">{job.get('jobName', '')}</div>
  <div style="font-size: 13px; color: #666; line-height: 1.4;">{description}</div>
  <div style="display: flex; gap: 8px; margin-top: 12px; padding-top: 12px; border-top: 1px solid #f0f0f0;">
    <a href="{hub_link}" style="display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600; text-decoration: none; padding: 8px 14px; border-radius: 999px; background: #f5f5f5; color: #666;">
      {update_svg} UPDATE
    </a>
    {teams_button}
  </div>
</div>'''


def _week_item(job, hub_link):
    """Build HTML for a 'rest of week' list item."""
    return f'''<li style="font-size: 14px; color: #333; padding: 6px 0; display: flex; align-items: center; gap: 8px; list-style: none;">
  <span style="color: {BRAND_RED}; font-weight: bold;">•</span>
  <a href="{hub_link}" style="text-decoration: none; display: inline;">
    <span style="font-weight: 600; color: {BRAND_RED}; text-decoration: underline; text-decoration-color: rgba(237, 28, 36, 0.3);">{job.get('jobNumber', '')}</span>
  </a>
  <span style="color: #666;">– {job.get('jobName', '')}</span>
  <span style="font-size: 12px; color: #999; margin-left: auto;">{job.get('status', '')}</span>
</li>'''


def _section_subtitle(text):
    """Build section subtitle (MEETINGS, JOBS DUE)."""
    return f'<div style="font-size: 12px; font-weight: 600; color: #666; text-transform: uppercase; letter-spacing: 0.5px; margin: 16px 0 8px 4px;">{text}</div>'


def _empty_state(text):
    """Build empty state message."""
    return f'<div style="background: white; border-radius: 16px; padding: 20px; text-align: center; color: #999; font-size: 14px;">{text}</div>'


# ===================
# MAIN BUILDER
# ===================

def build_todo_email(jobs, meetings, job_links, next_day_label='Tomorrow'):
    """
    Build the complete TO DO email HTML.
    
    Args:
        jobs: {'today': [...], 'tomorrow': [...], 'week': [...]}
        meetings: {'today': [...], 'tomorrow': [...]}
        job_links: dict mapping job_number -> hub_link
        next_day_label: 'Tomorrow' or 'Monday'
    
    Returns:
        Complete HTML string
    """
    
    # === TODAY SECTION ===
    today_html = '<div style="font-size: 18px; font-weight: 600; color: #1a1a1a; margin: 0 0 16px 0;">Today</div>'
    
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
    tomorrow_html = f'''<div style="margin-top: 24px;">
  <div style="font-size: 18px; font-weight: 600; color: #1a1a1a; margin: 0 0 16px 0;">{next_day_label}</div>'''
    
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
    
    tomorrow_html += '</div>'
    
    # === ALSO THIS WEEK SECTION ===
    week_html = ''
    if jobs.get('week'):
        week_html = '''<div style="margin-top: 24px; padding-top: 20px; border-top: 1px dashed #ccc;">
  <div style="font-size: 14px; font-weight: 600; color: #666; margin: 0 0 12px 0;">Also due this week</div>
  <ul style="margin: 0; padding: 0 0 0 4px; list-style: none;">'''
        
        for job in jobs['week']:
            hub_link = job_links.get(job.get('jobNumber'), '#')
            week_html += _week_item(job, hub_link)
        
        week_html += '</ul></div>'
    
    # === COMPLETE EMAIL ===
    email_html = f'''<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #e5e5e5; padding: 40px 20px; margin: 0;">
  <div style="max-width: 500px; margin: 0 auto; background: #f5f5f5; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
    
    <!-- Header -->
    <div style="background: {BRAND_RED}; color: white; padding: 24px; text-align: center;">
      <h1 style="margin: 0; font-size: 28px; font-weight: 400; letter-spacing: 2px;">TO DO</h1>
      <div style="margin-top: 8px; font-size: 14px; opacity: 0.9;">{_get_today_formatted()}</div>
    </div>
    
    <!-- Body -->
    <div style="padding: 20px;">
      {today_html}
      {tomorrow_html}
      {week_html}
    </div>
    
    <!-- Footer -->
    <div style="text-align: center; padding: 20px; color: #999; font-size: 12px;">
      Sent by Dot
    </div>
    
  </div>
</body>
</html>'''
    
    return email_html
