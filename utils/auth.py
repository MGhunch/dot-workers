"""
Dot Workers - Auth Utils
Token generation for Hub deep links.
"""

import os
import time
import hashlib
import base64

# ===================
# CONFIG
# ===================

TOKEN_SECRET = os.environ.get('TOKEN_SECRET', '')
TOKEN_EXPIRY_DAYS = int(os.environ.get('TOKEN_EXPIRY_DAYS', '7'))
HUB_URL = os.environ.get('HUB_URL', 'https://dot.hunch.co.nz')


# ===================
# TOKEN GENERATION
# ===================

def generate_token(email, client_code='ALL', first_name='User', access_level='Full'):
    """
    Generate a signed token for Hub deep links.
    
    Token contains: email|client_code|first_name|access_level|expires|signature
    
    Args:
        email: User's email address
        client_code: Client code or 'ALL' for full access
        first_name: User's first name (for greeting)
        access_level: 'Full', 'Client WIP', or 'Client Tracker'
    
    Returns:
        Base64 encoded token string
    """
    if not TOKEN_SECRET:
        print("[auth] WARNING: TOKEN_SECRET not configured")
        return None
    
    expires = int(time.time()) + (TOKEN_EXPIRY_DAYS * 24 * 60 * 60)
    data = f"{email}|{client_code}|{first_name}|{access_level}|{expires}"
    sig = hashlib.sha256(f"{data}|{TOKEN_SECRET}".encode()).hexdigest()[:8]
    token_data = f"{data}|{sig}"
    token = base64.urlsafe_b64encode(token_data.encode()).decode().rstrip('=')
    
    return token


def generate_job_link(job_number, email, client_code='ALL', first_name='User', access_level='Full'):
    """
    Generate a full Hub deep link for a job.
    
    Args:
        job_number: e.g., "SKY 018"
        email, client_code, first_name, access_level: for token
    
    Returns:
        Full URL: https://hub.hunch.co.nz/job/SKY018?t=<token>
    """
    token = generate_token(email, client_code, first_name, access_level)
    
    if not token:
        # Fallback to non-authenticated link
        job_slug = job_number.replace(' ', '')
        return f"{HUB_URL}/?job={job_slug}"
    
    # Job slug without space: "SKY 018" -> "SKY018"
    job_slug = job_number.replace(' ', '')
    
    return f"{HUB_URL}/job/{job_slug}?t={token}"
