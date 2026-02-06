"""
Client WIP Email Builder
Generates HTML email with active jobs grouped by section.
Styled to match Dot's standard email (same as TO DO).
"""

# ===================
# CONFIG
# ===================

BRAND_RED = '#ED1C24'
DARK_GREY = '#333'
LOGO_URL = "https://raw.githubusercontent.com/MGhunch/dot-hub/main/images/ai2-logo.png"
ASK_DOT_HEADER = "https://raw.githubusercontent.com/MGhunch/dot-hub/main/images/Askdot-header.png"

SUBJECT_LINE = "Latest WIP from Hunch"


# ===================
# HELPERS
# ===================

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


def _section_header(text):
    """Build section header - dark grey, caps, letter-spacing 0.1."""
    return f'<div style="font-size: 13px; font-weight: 600; color: {BRAND_RED}; text-transform: uppercase; letter-spacing: 0.1em; margin: 28px 0 12px 0;">{text}</div>'


def _job_card(job, hub_link):
    """Build HTML for a job card - clickable, with description."""
    description = job.get('description', '')
    if len(description) > 120:
        description = description[:117] + '...'

    job_number = job.get('jobNumber', '')
    job_name = job.get('jobName', '')

    return f'''<a href="{hub_link}" style="display: block; text-decoration: none; color: inherit; background: #f9f9f9; border-radius: 12px; padding: 16px 18px; margin-bottom: 10px; border-left: 3px solid {BRAND_RED};">
  <div style="margin-bottom: 8px;">
    <span style="font-size: 15px; font-weight: 600; color: #1a1a1a;">{job_number}</span>
    <span style="color: #ccc; margin: 0 8px;">&middot;</span>
    <span style="font-size: 15px; font-weight: 600; color: #1a1a1a;">{job_name}</span>
  </div>
  <div style="font-size: 15px; color: #666; line-height: 1.4; margin-bottom: 8px;">{description}</div>
  <div style="font-size: 13px; font-weight: 600; color: {BRAND_RED};">View details &rsaquo;</div>
</a>'''


# ===================
# MAIN BUILDER
# ===================

def build_wip_email(jobs, job_links, first_name='there', custom_note=None):
    """
    Build the complete client WIP email HTML.

    Args:
        jobs: {'with_hunch': [...], 'with_you': [...], 'on_hold': [...], 'upcoming': [...]}
        job_links: dict mapping job_number -> hub_link
        first_name: recipient's first name
        custom_note: optional personal note from sender

    Returns:
        Complete HTML string
    """

    # === INTRO ===
    intro_html = f'<p style="margin: 0 0 6px 0; font-size: 16px;">Hey {first_name},</p>'

    if custom_note:
        intro_html += f'<p style="margin: 0 0 16px 0; font-size: 16px; color: #333;">{custom_note}</p>'

    # === SECTIONS ===
    sections_html = ''

    # With Hunch
    if jobs.get('with_hunch'):
        sections_html += _section_header('With Hunch')
        for job in jobs['with_hunch']:
            hub_link = job_links.get(job.get('jobNumber'), '#')
            sections_html += _job_card(job, hub_link)

    # With You
    if jobs.get('with_you'):
        sections_html += _section_header('With You')
        for job in jobs['with_you']:
            hub_link = job_links.get(job.get('jobNumber'), '#')
            sections_html += _job_card(job, hub_link)

    # On Hold
    if jobs.get('on_hold'):
        sections_html += _section_header('On Hold')
        for job in jobs['on_hold']:
            hub_link = job_links.get(job.get('jobNumber'), '#')
            sections_html += _job_card(job, hub_link)

    # Upcoming
    if jobs.get('upcoming'):
        sections_html += _section_header('Upcoming')
        for job in jobs['upcoming']:
            hub_link = job_links.get(job.get('jobNumber'), '#')
            sections_html += _job_card(job, hub_link)

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
{sections_html}
{_footer()}

</div>

</body>
</html>'''

    return email_html
