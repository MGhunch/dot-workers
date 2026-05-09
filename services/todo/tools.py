"""
Dot Workers - Todo Classifier Tools
Tools the worker's todo classifier can call to disambiguate dumps.

Ported from dot-brain/traffic.py — only the two tools the todo classifier
needs (search_people, get_client_detail). Self-contained: own httpx calls,
no dependency on utils/airtable.

Used by services/todo/add_handler.py for the tool-use loop.
"""

import os
import httpx


# ===================
# CONFIG
# ===================

AIRTABLE_API_KEY = os.environ.get('AIRTABLE_API_KEY')
AIRTABLE_BASE_ID = os.environ.get('AIRTABLE_BASE_ID', 'app8CI7NAZqhQ4G1Y')
TIMEOUT = 10.0


def _headers():
    return {
        'Authorization': f'Bearer {AIRTABLE_API_KEY}',
        'Content-Type': 'application/json'
    }


def _url(table):
    return f'https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{table}'


# ===================
# TOOL: search_people
# ===================

def tool_search_people(client_code=None, search_term=None):
    """
    Search the People table by client code and/or name/email term.
    Returns {count, people: [{name, email, phone, clientCode}]}.
    """
    try:
        filters = ["{Active} = TRUE()"]
        if client_code:
            # One NZ has three divisions — match any of them when ONE is given
            if client_code in ('ONE', 'ONB', 'ONS'):
                filters.append(
                    "OR({Client Link} = 'ONE', {Client Link} = 'ONB', {Client Link} = 'ONS')"
                )
            else:
                filters.append(f"{{Client Link}} = '{client_code}'")

        formula = f"AND({', '.join(filters)})" if len(filters) > 1 else filters[0]
        params = {'filterByFormula': formula}

        all_people = []
        offset = None

        while True:
            if offset:
                params['offset'] = offset

            response = httpx.get(
                _url('People'),
                headers=_headers(),
                params=params,
                timeout=TIMEOUT
            )
            response.raise_for_status()
            data = response.json()

            for record in data.get('records', []):
                fields = record.get('fields', {})
                name = fields.get('Name', fields.get('Full name', ''))
                if not name:
                    continue

                if search_term:
                    searchable = f"{name} {fields.get('Email Address', '')}".lower()
                    if search_term.lower() not in searchable:
                        continue

                all_people.append({
                    'name': name,
                    'email': fields.get('Email Address', ''),
                    'phone': fields.get('Phone Number', ''),
                    'clientCode': fields.get('Client Link', '')
                })

            offset = data.get('offset')
            if not offset:
                break

        return {'count': len(all_people), 'people': all_people}

    except Exception as e:
        return {'error': str(e)}


# ===================
# TOOL: get_client_detail
# ===================

def tool_get_client_detail(client_code):
    """
    Confirm a client code resolves to a real client.
    Returns {code, name} or {error}. Stripped down from Brain's full version —
    the todo classifier only needs to verify the code is real, not budget data.
    """
    try:
        params = {
            'filterByFormula': f"{{Client code}} = '{client_code}'",
            'maxRecords': 1
        }
        response = httpx.get(
            _url('Clients'),
            headers=_headers(),
            params=params,
            timeout=TIMEOUT
        )
        response.raise_for_status()

        records = response.json().get('records', [])
        if not records:
            return {'error': f'Client {client_code} not found'}

        fields = records[0].get('fields', {})
        return {
            'code': client_code,
            'name': fields.get('Clients', '')
        }

    except Exception as e:
        return {'error': str(e)}


# ===================
# TOOL DEFINITIONS (for Anthropic API)
# ===================

CLAUDE_TOOLS = [
    {
        "name": "search_people",
        "description": (
            "Search People table to disambiguate a person mentioned in a todo dump. "
            "Use when a name appears without explicit client context (e.g., 'Email Keith "
            "re strat pack') and you want to know which client they belong to. Returns "
            "matching people with their client codes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "client_code": {
                    "type": "string",
                    "description": (
                        "Optional. Filter by client code (e.g., 'SKY', 'TOW'). "
                        "For One NZ, ONE/ONB/ONS all match together."
                    )
                },
                "search_term": {
                    "type": "string",
                    "description": (
                        "Optional. Substring match against name and email (case-insensitive)."
                    )
                }
            },
            "required": []
        }
    },
    {
        "name": "get_client_detail",
        "description": (
            "Confirm a client code resolves to a real client. Returns code and name, "
            "or error if not found. Rarely needed — only when you want to verify a "
            "code before assigning it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "client_code": {
                    "type": "string",
                    "description": "The 3-letter client code (e.g., 'SKY', 'TOW', 'ONE')."
                }
            },
            "required": ["client_code"]
        }
    }
]


# ===================
# DISPATCHER
# ===================

def execute_tool(tool_name, tool_input):
    """Run a tool by name and return the result dict."""
    print(f"[todo-tools] {tool_name} input: {tool_input}")

    if tool_name == 'search_people':
        result = tool_search_people(
            client_code=tool_input.get('client_code'),
            search_term=tool_input.get('search_term')
        )
    elif tool_name == 'get_client_detail':
        result = tool_get_client_detail(tool_input.get('client_code'))
    else:
        result = {'error': f'Unknown tool: {tool_name}'}

    if isinstance(result, dict):
        print(f"[todo-tools] {tool_name} result keys: {list(result.keys())}")
    return result
