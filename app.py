"""
Dot Workers
Workers do work. Brain already decided.

Pattern: GO IN → DO THING → SEND COMMS → GET OUT
"""

from flask import Flask, request, jsonify
from flask_cors import CORS

from services.update.handler import process_update

app = Flask(__name__)
CORS(app)


# ===================
# ROUTES
# ===================

@app.route('/update', methods=['POST'])
def update():
    """Process job update"""
    return process_update(request.get_json())


# Future services:
# @app.route('/newjob', methods=['POST'])
# def newjob():
#     return process_newjob(request.get_json())


# ===================
# HEALTH
# ===================

@app.route('/', methods=['GET'])
@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'Dot Workers',
        'version': '2.0',
        'services': ['update']
    })


# ===================
# RUN
# ===================

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
