"""A local stdlib HTTP server standing in for Oracle Fusion Cloud SCM's REST
API (items, work orders), shaped like the published resource paths under
/fscmRestApi/resources/11.13.18.05/: offset/limit pagination, a `hasMore`
flag. No production Oracle Fusion instance is involved anywhere in this
repo; this is a mock, not a client against a real tenant.

Runs as a background thread inside the calling process rather than a
separate OS process, so there is no PID to track or kill: `stop_server`
just shuts the server down and joins the thread.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

DEFAULT_PAGE_SIZE = 100


def _paginate(items, offset, limit):
    page = items[offset:offset + limit]
    has_more = offset + limit < len(items)
    return page, has_more


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        offset = int(qs.get("offset", ["0"])[0])
        limit = int(qs.get("limit", [str(DEFAULT_PAGE_SIZE)])[0])
        resource = parsed.path.rstrip("/").rsplit("/", 1)[-1]
        rows = self.server.resources.get(resource)
        if rows is None:
            self.send_response(404)
            self.end_headers()
            return
        page, has_more = _paginate(rows, offset, limit)
        body = json.dumps({"items": page, "hasMore": has_more, "offset": offset, "limit": limit}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start_server(resources):
    """`resources`: dict[str, list[dict]] keyed by Fusion resource name
    (e.g. "items", "workOrders"). Binds to an OS-assigned port."""
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    server.resources = resources
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def stop_server(server, thread):
    server.shutdown()
    thread.join(timeout=5)
    server.server_close()
