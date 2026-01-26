"""
Sass from the Stars - Horoscope Service
A fun horoscope service powered by recycled wisdom.

Endpoints:
- POST /horoscope - Get a horoscope for a star sign
- GET /signs - List valid star signs
"""

from flask import Flask, request, jsonify
import json
import random
from datetime import date

app = Flask(__name__)

# Load horoscopes
with open('horoscopes.json', 'r') as f:
    HOROSCOPES = json.load(f)

VALID_SIGNS = list(HOROSCOPES.keys())

DISCLAIMER = "Some insights may be recycled. But... it's horoscopes, right?"


def get_daily_horoscope(sign: str) -> str:
    """
    Get a horoscope for a sign that stays consistent for the whole day.
    Uses date as seed so everyone with same sign gets same horoscope that day.
    """
    sign = sign.lower().strip()
    if sign not in HOROSCOPES:
        return None
    
    # Seed with date + sign so it's consistent per day per sign
    today = date.today().isoformat()
    seed = hash(f"{today}-{sign}")
    random.seed(seed)
    
    horoscope = random.choice(HOROSCOPES[sign])
    
    # Reset random seed
    random.seed()
    
    return horoscope


def get_random_horoscope(sign: str) -> str:
    """
    Get a completely random horoscope for a sign.
    """
    sign = sign.lower().strip()
    if sign not in HOROSCOPES:
        return None
    
    return random.choice(HOROSCOPES[sign])


@app.route('/horoscope', methods=['POST'])
def horoscope():
    """
    Get a horoscope for a star sign.
    
    Request body:
    {
        "sign": "aries",
        "mode": "daily" | "random"  (optional, defaults to "daily")
    }
    
    Response:
    {
        "sign": "aries",
        "horoscope": "...",
        "disclaimer": "Some insights may be recycled..."
    }
    """
    try:
        data = request.get_json() or {}
        sign = data.get('sign', '').lower().strip()
        mode = data.get('mode', 'daily').lower()
        
        if not sign:
            return jsonify({
                'error': 'Missing sign parameter',
                'valid_signs': VALID_SIGNS
            }), 400
        
        if sign not in VALID_SIGNS:
            return jsonify({
                'error': f'Invalid sign: {sign}',
                'valid_signs': VALID_SIGNS
            }), 400
        
        if mode == 'random':
            horoscope_text = get_random_horoscope(sign)
        else:
            horoscope_text = get_daily_horoscope(sign)
        
        return jsonify({
            'sign': sign.capitalize(),
            'horoscope': horoscope_text,
            'disclaimer': DISCLAIMER
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/signs', methods=['GET'])
def signs():
    """
    List all valid star signs.
    """
    return jsonify({
        'signs': [s.capitalize() for s in VALID_SIGNS]
    })


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'sass-from-the-stars',
        'horoscope_count': sum(len(h) for h in HOROSCOPES.values())
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
