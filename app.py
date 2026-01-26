"""
Dot Workers
Service endpoints for Dot's worker tasks.

Each service lives in /services and handles a specific job type.
This app exposes them as endpoints for Brain to call.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


# ===================
# HEALTH CHECK
# ===================

@app.route('/', methods=['GET'])
@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'Dot Workers',
        'endpoints': ['/update', '/horoscope']
    })


# ===================
# UPDATE SERVICE
# ===================

@app.route('/update', methods=['POST'])
def update():
    """Process a job update"""
    from services.update.handler import process_update
    data = request.get_json()
    return process_update(data)


# ===================
# HOROSCOPE SERVICE
# ===================

@app.route('/horoscope', methods=['POST'])
def horoscope():
    """Get a horoscope for a star sign"""
    from services.horoscopes.handler import get_horoscope
    data = request.get_json()
    return get_horoscope(data)


# ===================
# RUN
# ===================

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
