"""
Dot Workers
Workers do work. Brain already decided.

Pattern: GO IN → DO THING → SEND COMMS → GET OUT
"""

from flask import Flask, request, jsonify
from flask_cors import CORS

from services.update.handler import process_update
from utils.setup import setup_teams_channel

app = Flask(__name__)
CORS(app)


# ===================
# ROUTES
# ===================

@app.route('/update', methods=['POST'])
def update():
    """Process job update"""
    return process_update(request.get_json())


@app.route('/setup', methods=['POST'])
def setup():
    """Setup Teams channel for new job"""
    data = request.get_json()
    result = setup_teams_channel(
        data.get('teamId'),
        data.get('jobNumber'),
        data.get('jobName'),
        data.get('recordId')
    )
    return jsonify(result)


# ===================
# HEALTH
# ===================

@app.route('/', methods=['GET'])
@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'Dot Workers',
        'version': '2.1',
        'services': ['update', 'setup']
    })


# ===================
# RUN
# ===================

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
