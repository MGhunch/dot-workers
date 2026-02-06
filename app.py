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
        'endpoints': ['/update', '/horoscope', '/setup', '/file', '/todo/email', '/wip/email']
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
# SETUP SERVICE
# ===================

@app.route('/setup', methods=['POST'])
def setup():
    """Set up a new job from an email brief"""
    from services.setup.handler import process_setup
    data = request.get_json()
    return process_setup(data)


# ===================
# FILE SERVICE
# ===================

@app.route('/file', methods=['POST'])
def file_attachments():
    """File attachments to SharePoint job folder"""
    from services.file.handler import process_file
    data = request.get_json()
    return process_file(data)


# ===================
# TO DO EMAIL SERVICE
# ===================

@app.route('/todo/email', methods=['GET'])
def todo_email():
    """Send daily TO DO email with jobs + meetings"""
    from services.todo.handler import send_todo_email
    return send_todo_email()


# ===================
# WIP EMAIL SERVICE
# ===================

@app.route('/wip/email', methods=['POST'])
def wip_email():
    """Send WIP email to client contacts"""
    from services.wip_email.handler import send_wip_email
    data = request.get_json()
    return send_wip_email(data)


# ===================
# RUN
# ===================

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
