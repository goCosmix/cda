import json
import threading
import time
import traceback
from pathlib import Path
from urllib.parse import parse_qs

from cda.kernel.pmf_kernel import PMFKernel
from cda.ui.actions import run_action_background
from cda.ui.db import (
    get_overview, get_sessions, get_session_detail, get_search_results,
    get_workspaces, get_memory, get_tool_calls,
    get_alerts, get_tokens, query_rows,
)
from cda.ui.templates import INDEX_HTML, PAGE_REGISTRY_JS

_static_dir = Path(__file__).parent / 'static'
_CSS = (_static_dir / 'web.css').read_text(encoding='utf-8')
_STATIC_JS = (_static_dir / 'web.js').read_text(encoding='utf-8')
_APP_JS = PAGE_REGISTRY_JS + _STATIC_JS

kernel = PMFKernel()


def application(environ, start_response):
    """WSGI application."""
    method = environ['REQUEST_METHOD']
    path = environ['PATH_INFO']
    query = parse_qs(environ.get('QUERY_STRING', ''))

    try:
        if path == '/':
            response = (
                INDEX_HTML
                .replace('{{STYLE_CSS}}', _CSS)
                .replace('{{APP_JS}}', _APP_JS)
                .encode('utf-8')
            )
            start_response('200 OK', [('Content-Type', 'text/html; charset=utf-8')])
            return [response]

        elif path == '/api/overview':
            data = get_overview()
            response = json.dumps(data).encode('utf-8')
            start_response('200 OK', [('Content-Type', 'application/json')])
            return [response]

        elif path == '/api/sessions':
            limit = int(query.get('limit', ['50'])[0])
            offset = int(query.get('offset', ['0'])[0])
            data = get_sessions(limit, offset)
            response = json.dumps(data).encode('utf-8')
            start_response('200 OK', [('Content-Type', 'application/json')])
            return [response]

        elif path == '/api/search':
            q = query.get('q', [''])[0]
            data = get_search_results(q)
            response = json.dumps(data).encode('utf-8')
            start_response('200 OK', [('Content-Type', 'application/json')])
            return [response]

        elif path == '/api/workspaces':
            data = get_workspaces()
            response = json.dumps(data).encode('utf-8')
            start_response('200 OK', [('Content-Type', 'application/json')])
            return [response]

        elif path == '/api/session':
            session_id = query.get('session_id', [''])[0]
            data = get_session_detail(session_id)
            response = json.dumps(data).encode('utf-8')
            start_response('200 OK', [('Content-Type', 'application/json')])
            return [response]

        elif path == '/api/tools':
            q = query.get('q', [''])[0]
            data = get_tool_calls(q if q else None)
            response = json.dumps(data).encode('utf-8')
            start_response('200 OK', [('Content-Type', 'application/json')])
            return [response]

        elif path == '/api/memory':
            data = get_memory()
            response = json.dumps(data).encode('utf-8')
            start_response('200 OK', [('Content-Type', 'application/json')])
            return [response]

        elif path == '/api/tokens':
            session_id = query.get('session_id', [None])[0]
            data = get_tokens(session_id)
            response = json.dumps(data).encode('utf-8')
            start_response('200 OK', [('Content-Type', 'application/json')])
            return [response]

        elif path == '/api/alerts':
            data = get_alerts()
            response = json.dumps(data).encode('utf-8')
            start_response('200 OK', [('Content-Type', 'application/json')])
            return [response]

        elif path == '/api/action' and method == 'POST':
            body = environ['wsgi.input'].read()
            payload = json.loads(body.decode('utf-8'))
            action = payload.get('action', '')

            action_id = f"{action}_{int(time.time() * 1000)}"
            thread = threading.Thread(target=run_action_background, args=(action_id, action))
            thread.daemon = True
            thread.start()

            response = json.dumps({
                "ok": True,
                "action": action,
                "action_id": action_id,
                "message": f"Started {action}..."
            }).encode('utf-8')
            start_response('200 OK', [('Content-Type', 'application/json')])
            return [response]

        elif path == '/api/query' and method == 'POST':
            body = environ['wsgi.input'].read()
            payload = json.loads(body.decode('utf-8'))
            sql = payload.get('sql', '')

            rows = query_rows(sql)
            response = json.dumps({"rows": rows}).encode('utf-8')
            start_response('200 OK', [('Content-Type', 'application/json')])
            return [response]

        elif path == '/api/pipeline/status' and method == 'GET':
            from cda.pipeline.backfill import get_pipeline_status
            data = get_pipeline_status()
            response = json.dumps(data).encode('utf-8')
            start_response('200 OK', [('Content-Type', 'application/json')])
            return [response]

        elif path == '/api/pmf/services' and method == 'GET':
            try:
                services = kernel.services()
                response = json.dumps({"services": services}).encode('utf-8')
                start_response('200 OK', [('Content-Type', 'application/json')])
                return [response]
            except Exception as e:
                response = json.dumps({"error": str(e)}).encode('utf-8')
                start_response('500 Internal Server Error', [('Content-Type', 'application/json')])
                return [response]

        elif path == '/api/pmf/service' and method == 'POST':
            body = environ['wsgi.input'].read()
            payload = json.loads(body.decode('utf-8'))
            service_id = payload.get('service')
            action = payload.get('action')
            if not service_id or not action:
                raise ValueError('service and action are required')
            try:
                if action == 'start':
                    result = kernel.start_service(service_id, options=payload.get('options', {}))
                elif action == 'stop':
                    result = kernel.stop_service(service_id)
                elif action == 'restart':
                    result = kernel.restart_service(service_id, options=payload.get('options', {}))
                else:
                    raise ValueError('unsupported action: ' + action)
                response = json.dumps({
                    "ok": True,
                    "service": service_id,
                    "action": action,
                    "message": f"{action} requested for {service_id}",
                    "result": result,
                }).encode('utf-8')
                start_response('200 OK', [('Content-Type', 'application/json')])
                return [response]
            except Exception as e:
                response = json.dumps({"error": str(e)}).encode('utf-8')
                start_response('500 Internal Server Error', [('Content-Type', 'application/json')])
                return [response]

        else:
            response = b'Not Found'
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            return [response]

    except Exception as e:
        traceback.print_exc()
        response = json.dumps({"error": str(e)}).encode('utf-8')
        start_response('500 Internal Server Error', [('Content-Type', 'application/json')])
        return [response]
