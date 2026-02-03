"""
Horoscopes Service
Returns sassy horoscopes from the Astrobot.

GO IN → PICK SASS → GET OUT

Simple service - no Airtable, no Teams, no email.
Just returns a horoscope for the requested sign.
"""

from flask import jsonify
import json
import os
import random
from datetime import date

# ===================
# LOAD DATA
# ===================

HOROSCOPES_PATH = os.path.join(os.path.dirname(__file__), 'horoscopes.json')
with open(HOROSCOPES_PATH, 'r') as f:
    HOROSCOPES = json.load(f)

VALID_SIGNS = list(HOROSCOPES.keys())

INTRO = "Here's some spicy star stuff from the astrobot..."
DISCLAIMER = "Some insights are recycled. But that's star signs, right?"


# ===================
# HELPERS
# ===================

def _get_daily_horoscope(sign: str) -> str:
    """
    Get a horoscope that stays consistent for the whole day.
    Uses date as seed so everyone with same sign gets same horoscope that day.
    """
    today = date.today().isoformat()
    seed = hash(f"{today}-{sign}")
    random.seed(seed)
    horoscope = random.choice(HOROSCOPES[sign])
    random.seed()  # Reset
    return horoscope


def _get_random_horoscope(sign: str) -> str:
    """
    Get a completely random horoscope.
    """
    return random.choice(HOROSCOPES[sign])


# ===================
# MAIN HANDLER
# ===================

def get_horoscope(data):
    """
    Get a horoscope for a star sign.
    
    Input:
        data: dict with 'sign' and optional 'mode' ('daily' or 'random')
    
    Returns:
        Flask jsonify response with intro, sign, horoscope, disclaimer
    """
    sign = data.get('sign', '').lower().strip()
    mode = data.get('mode', 'daily').lower()
    
    print(f"[horoscopes] === GETTING SASS ===")
    print(f"[horoscopes] Sign: {sign}")
    print(f"[horoscopes] Mode: {mode}")
    
    # Validate sign
    if not sign:
        return jsonify({
            'success': False,
            'error': 'No sign provided',
            'valid_signs': VALID_SIGNS
        }), 400
    
    if sign not in VALID_SIGNS:
        return jsonify({
            'success': False,
            'error': f'Invalid sign: {sign}',
            'valid_signs': VALID_SIGNS
        }), 400
    
    # Get the sass
    if mode == 'random':
        horoscope = _get_random_horoscope(sign)
    else:
        horoscope = _get_daily_horoscope(sign)
    
    print(f"[horoscopes] Returning: {horoscope[:50]}...")
    
    return jsonify({
        'success': True,
        'intro': INTRO,
        'sign': sign.capitalize(),
        'horoscope': horoscope,
        'disclaimer': DISCLAIMER
    })
