"""
Add To Do Service
Classifies a raw todo dump and writes one or more records to the Todo table.

GO IN → CLASSIFY (CLAUDE) → WRITE EACH → GET OUT

Endpoint: POST /todo
Body: {"dump": "raw text"}

Returns:
  {
    "success": true,
    "saved": [
      {"id": "rec...", "title": "...", "bucket": "...", "client": "...", "urgent": false, "confidence": "..."},
      ...
    ],
    "count": N,
    "failed": [...] | null
  }

Or on error:
  {"success": false, "error": "..."}

Classification logic lives in add_prompt.txt (lifted from the todolist skill).
The endpoint is the canonical write path — chat, email, skill all call here.
"""

import os
import json
import httpx
from flask import jsonify
from anthropic import Anthropic

from utils import airtable
from . import tools

# ===================
# CLAUDE CLIENT
# ===================

client = Anthropic(
    api_key=os.environ.get('ANTHROPIC_API_KEY'),
    http_client=httpx.Client(timeout=60.0, follow_redirects=True)
)

# Load prompt
PROMPT_PATH = os.path.join(os.path.dirname(__file__), 'add_prompt.txt')
with open(PROMPT_PATH, 'r') as f:
    ADD_PROMPT = f.read()


# ===================
# HELPERS
# ===================

def _strip_markdown_json(content):
    """Strip markdown code fences from JSON response (Claude sometimes adds them despite being told not to)."""
    content = content.strip()
    if content.startswith('```'):
        content = content.split('\n', 1)[1] if '\n' in content else content[3:]
    if content.endswith('```'):
        content = content.rsplit('```', 1)[0]
    return content.strip()


# ===================
# MAIN HANDLER
# ===================

def add_todo(data):
    """
    Classify a raw todo dump and write one or more todos to Airtable.
    """
    dump = (data or {}).get('dump', '').strip()

    print(f"[todo-add] === ADDING TO DO ===")
    print(f"[todo-add] Dump: {dump[:120]}{'...' if len(dump) > 120 else ''}")

    if not dump:
        return jsonify({'success': False, 'error': 'No dump provided'}), 400

    try:
        # ===================
        # 1. CLASSIFY (with tool-loop for disambiguation)
        # ===================
        messages = [{'role': 'user', 'content': dump}]

        response = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=1500,
            temperature=0.1,
            system=ADD_PROMPT,
            messages=messages,
            tools=tools.CLAUDE_TOOLS
        )

        # Tool loop — keep going until Claude returns its final JSON
        max_rounds = 3
        rounds = 0
        while response.stop_reason == 'tool_use' and rounds < max_rounds:
            rounds += 1
            print(f"[todo-add] Tool round {rounds}")

            # Append assistant turn (preserves tool_use blocks)
            messages.append({'role': 'assistant', 'content': response.content})

            # Execute every tool call in this turn
            tool_results = []
            for block in response.content:
                if block.type == 'tool_use':
                    result = tools.execute_tool(block.name, block.input)
                    tool_results.append({
                        'type': 'tool_result',
                        'tool_use_id': block.id,
                        'content': json.dumps(result)
                    })

            messages.append({'role': 'user', 'content': tool_results})

            response = client.messages.create(
                model='claude-sonnet-4-6',
                max_tokens=1500,
                temperature=0.1,
                system=ADD_PROMPT,
                messages=messages,
                tools=tools.CLAUDE_TOOLS
            )

        if rounds >= max_rounds and response.stop_reason == 'tool_use':
            print(f"[todo-add] Hit max tool rounds ({max_rounds}) — using last response")

        # Extract final text from response (first text block)
        content = ''
        for block in response.content:
            if hasattr(block, 'text') and block.text:
                content = block.text
                break

        if not content:
            print(f"[todo-add] Classifier returned no text (stop_reason={response.stop_reason})")
            return jsonify({
                'success': False,
                'error': f'Classifier returned no text (stop_reason={response.stop_reason})'
            }), 500

        content = _strip_markdown_json(content)
        todos = json.loads(content)

        if not isinstance(todos, list):
            print(f"[todo-add] Claude returned non-list: {type(todos).__name__}")
            return jsonify({
                'success': False,
                'error': 'Classifier did not return a list'
            }), 500

        if len(todos) == 0:
            print(f"[todo-add] No actionable todos in dump")
            return jsonify({
                'success': True,
                'saved': [],
                'count': 0,
                'message': 'No actionable todos found'
            })

        print(f"[todo-add] Classifier returned {len(todos)} todo(s)")

        # ===================
        # 2. WRITE EACH
        # ===================
        saved = []
        failed = []

        for todo in todos:
            title = (todo.get('title') or '').strip()
            bucket = todo.get('bucket', 'OTHER')
            client_code = todo.get('client')
            urgent = bool(todo.get('urgent', False))
            confidence = todo.get('confidence', 'Low')

            if not title:
                print(f"[todo-add] Skipping todo with no title: {todo}")
                failed.append({'todo': todo, 'error': 'Missing title'})
                continue

            record_id, error = airtable.create_todo(
                title=title,
                bucket=bucket,
                client_code=client_code,
                urgent=urgent,
                confidence=confidence
            )

            if error:
                print(f"[todo-add] Failed '{title}': {error}")
                failed.append({'todo': todo, 'error': error})
            else:
                print(f"[todo-add] Saved '{title}' ({record_id})")
                saved.append({
                    'id': record_id,
                    'title': title,
                    'bucket': bucket,
                    'client': client_code,
                    'urgent': urgent,
                    'confidence': confidence
                })

        # ===================
        # 3. RESPOND
        # ===================
        print(f"[todo-add] Done: {len(saved)} saved, {len(failed)} failed")
        return jsonify({
            'success': len(saved) > 0,
            'saved': saved,
            'count': len(saved),
            'failed': failed if failed else None
        })

    except json.JSONDecodeError as e:
        print(f"[todo-add] JSON decode error: {e}")
        return jsonify({
            'success': False,
            'error': f'Classifier returned invalid JSON: {str(e)}'
        }), 500

    except Exception as e:
        print(f"[todo-add] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
