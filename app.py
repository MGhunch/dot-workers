"""
Dot Workers - Flask App
Routes incoming requests to the appropriate service handlers.

Brain calls these endpoints via HTTP POST.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS

# Import handlers
from services.update.handler import process_update
from services.setup.handler import process_setup
from services.file.handler import process_file, process_folder
from services.horoscopes.handler import get_horoscope
from services.todo.handler import send_todo_email
from services.todo.add_handler import add_todo
from services.upload.handler import process_upload
from services.wip_email.handler import send_wip_email
from services.spend_chart import (
    generate_spend_chart,
    generate_hunch_spend_chart,
    generate_group_spend_chart,
)

# ===================
# APP SETUP
# ===================

app = Flask(__name__)
CORS(app)


# ===================
# HEALTH CHECK
# ===================

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'dot-workers'})


@app.route('/', methods=['GET'])
def index():
    return jsonify({
        'service': 'dot-workers',
        'status': 'running',
        'endpoints': ['/update', '/setup', '/file', '/folder', '/horoscope', '/todo', '/todo/email', '/upload', '/wip/email', '/charts/spend', '/charts/spend/hunch', '/charts/spend/group']
    })


# ===================
# WORKER ENDPOINTS
# ===================

@app.route('/update', methods=['POST'])
def update():
    """Process job updates from email."""
    return process_update(request.json)


@app.route('/setup', methods=['POST'])
def setup():
    """Create new jobs from email briefs."""
    return process_setup(request.json)


@app.route('/file', methods=['POST'])
def file():
    """File attachments to Dropbox."""
    return process_file(request.json)


@app.route('/folder', methods=['POST'])
def folder():
    """Create a Dropbox job folder for a new job (called by Hub /api/new-job)."""
    return process_folder(request.json)


@app.route('/horoscope', methods=['POST'])
def horoscope():
    """Get daily horoscope."""
    return get_horoscope(request.json)


@app.route('/todo', methods=['POST'])
def todo_add():
    """Add a to do (raw dump → classified records). Splits multi-task dumps."""
    return add_todo(request.json)


@app.route('/todo/email', methods=['POST'])
def todo():
    """Send TO DO email."""
    return send_todo_email(request.json)


@app.route('/upload', methods=['POST'])
def upload():
    """Handle file uploads from Hub."""
    return process_upload(request)


@app.route('/wip/email', methods=['POST'])
def wip_email():
    """Send WIP email to client."""
    return send_wip_email(request.json)



@app.route('/charts/spend', methods=['POST'])
def charts_spend():
    """Generate a YTD spend chart for one client. Returns base64 PNG."""
    return generate_spend_chart(request.json)


@app.route('/charts/spend/hunch', methods=['POST'])
def charts_spend_hunch():
    """Generate a rolling-12-month spend chart for the whole agency."""
    return generate_hunch_spend_chart(request.json or {})


@app.route('/charts/spend/group', methods=['POST'])
def charts_spend_group():
    """Generate a YTD spend chart for a group of client codes billed as one
    relationship. Body: {"group": "onenz" | "onenz-bm", "fy": "current"|"last"}."""
    return generate_group_spend_chart(request.json or {})


# ===================
# RUN
# ===================

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
