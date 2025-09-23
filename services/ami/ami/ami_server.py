import argparse
import importlib
import json
import logging
import os
import signal
import sys
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

import ayon_api
from shotgun_api3 import Shotgun

logger = logging.getLogger("proto-ami-server")


def json_dumps(data: Dict[str, Any]) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")


def _content_length(handler: BaseHTTPRequestHandler) -> int:
    try:
        return int(handler.headers.get("Content-Length") or "0")
    except ValueError:
        return 0


def drain_request_body(handler: BaseHTTPRequestHandler, max_bytes: int = 2 * 1024 * 1024) -> None:
    remaining = _content_length(handler)
    if remaining <= 0:
        return
    to_read = min(remaining, max_bytes)
    try:
        _ = handler.rfile.read(to_read)
    except Exception:
        pass


# b'user_id=121&user_login=pierrer@rvx.is&title=undefined&entity_type=Playlist&server_hostname=apavatn.shotgrid.autodesk.com&referrer_path=/detail/HumanUser/121&page_id=5703&session_uuid=9449dbc6-945d-11f0-ae27-0a58a9feac02&project_name=Flow_Pet_Project&project_id=122&target_column=code&ids=248&selected_ids=248&cols=code,locked,description,tags,updated_at,updated_by&view=Playlists&column_display_names=Playlist Name,Locked,Description,Tags,Date Updated,Updated by&sort_column=updated_at&sort_direction=desc&grouping_column=updated_at&grouping_method=week&grouping_direction=desc'

def read_form_body(handler: BaseHTTPRequestHandler, max_bytes: int = 2 * 1024 * 1024) -> Tuple[
    Optional[Dict[str, Any]], Optional[str]]:
    length = _content_length(handler)
    if length < 0:
        return None, "Invalid Content-Length header"
    if length == 0:
        return {}, None
    if length > max_bytes:
        drain_request_body(handler)
        return None, f"Payload too large: {length} > {max_bytes} bytes"

    raw = handler.rfile.read(length)
    try:
        parsed = parse_qs(raw.decode("utf-8"), keep_blank_values=True)
        normalized: Dict[str, Any] = {k: (v[0] if len(v) == 1 else v) for k, v in parsed.items()}
        return normalized, None
    except Exception as exc:
        return None, f"Invalid form data: {exc}"


def _wants_html(handler: BaseHTTPRequestHandler) -> bool:
    accept = (handler.headers.get("Accept") or "").lower()
    agent = (handler.headers.get("User-Agent") or "").lower()
    if "text/html" in accept:
        return True
    # Heuristic: browsers typically identify themselves this way
    if "mozilla" in agent or "safari" in agent or "chrome" in agent or "edge" in agent:
        return True
    return False


def _render_html_page(title: str, success: bool, message: str, lines: list[str], echo: Dict[str, Any]) -> bytes:
    # keep it inline, simple, and readable
    badge_color = "#16a34a" if success else "#dc2626"
    border_color = "#22c55e" if success else "#f87171"
    safe_pre = json.dumps(echo, ensure_ascii=False, indent=2)
    items_html = "".join(f"<li>{line}</li>" for line in lines)
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {{
    --bg: #0f172a;        /* slate-900 */
    --panel: #0b1220;     /* darker panel */
    --text: #e5e7eb;      /* gray-200 */
    --muted: #9ca3af;     /* gray-400 */
  }}
  html, body {{ height: 100%; }}
  body {{
    margin: 0; padding: 24px;
    background: radial-gradient(1200px 800px at 20% -10%, #1e293b 20%, var(--bg) 70%);
    color: var(--text); font: 15px/1.5 -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji", "Segoe UI Emoji";
  }}
  .wrap {{
    max-width: 860px; margin: 0 auto;
  }}
  .card {{
    background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 14px; box-shadow: 0 10px 30px rgba(0,0,0,0.35);
    overflow: hidden;
  }}
  .header {{
    display: flex; align-items: center; gap: 12px;
    padding: 18px 20px; border-bottom: 1px solid rgba(255,255,255,0.08);
    background: linear-gradient(180deg, rgba(0,0,0,0.2), rgba(0,0,0,0));
  }}
  .badge {{
    display: inline-block; padding: 6px 10px; font-weight: 600;
    color: white; background: {badge_color}; border-radius: 999px;
    border: 1px solid {border_color}; letter-spacing: 0.25px;
  }}
  h1 {{ font-size: 18px; margin: 0; }}
  .content {{ padding: 18px 20px 8px 20px; }}
  .message {{ color: var(--text); margin: 0 0 10px 0; }}
  .details {{ color: var(--muted); margin: 0 0 6px 16px; }}
  pre {{
    background: var(--panel);
    color: #d1d5db;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 14px; overflow: auto;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
  }}
  .footer {{
    padding: 10px 20px 16px 20px; color: var(--muted); font-size: 12px;
  }}
  a, a:visited {{ color: #93c5fd; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <div class="header">
        <span class="badge">{'Success' if success else 'Error'}</span>
        <h1>{title}</h1>
      </div>
      <div class="content">
        <p class="message">{message}</p>
        <ul class="details">
          {items_html}
        </ul>
        <pre>{safe_pre}</pre>
      </div>
      <div class="footer">
        ShotGrid AMI Prototype • {('All good.' if success else 'Please review and retry.')}
      </div>
    </div>
  </div>
</body>
</html>"""
    return html.encode("utf-8")


def get_sg_session():
    ayon_api_key = os.environ.get("AYON_API_KEY")
    ayon_server_url = os.environ.get("AYON_SERVER_URL")
    sg_url = os.environ.get("SG_URL")
    proxy_url = os.environ.get("HTTP_PROXY").replace("http://", "")
    if not ayon_api_key or not ayon_server_url:
        raise Exception("AYON_API_KEY and AYON_SERVER_URL are required")
    if not sg_url or not proxy_url:
        raise Exception("SHOTGUN URL and proxy URL are required")

    ayon_api.init_service(token=ayon_api_key, server_url=ayon_server_url)
    script_name = ayon_api.get_secret("flow_script_name")["value"]
    script_key = ayon_api.get_secret("flow_script_key")["value"]

    if not script_name or not script_key:
        raise Exception("Script name or key is not set")

    return Shotgun(sg_url, script_name=script_name, api_key=script_key, http_proxy=proxy_url)


class AmiRequestHandler(BaseHTTPRequestHandler):
    server_version = "ProtoAmiServer/0.3"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        logger.info("%s - %s", self.address_string(), fmt % args)

    def _apply_cors(self) -> None:
        origin = self.headers.get("Origin") or "*"
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-SG-Signature")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Max-Age", "600")

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._apply_cors()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path == "/health":
            payload = {"status": "ok"}
            body = json_dumps(payload)
            self.send_response(HTTPStatus.OK)
            self._apply_cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self._apply_cors()
            self.end_headers()
            return

        if path in ("/", "/ami"):
            query_data = parse_qs(parsed.query, keep_blank_values=True)
            data: Dict[str, Any] = {k: (v[0] if len(v) == 1 else v) for k, v in query_data.items()}
            content = self._build_html_for_result(data, success=True)
            self._send_html(HTTPStatus.OK, content)
            return

        body = json_dumps({"error": "Not found"})
        self.send_response(HTTPStatus.NOT_FOUND)
        self._apply_cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path not in ("/ami", "/action", "/"):
            drain_request_body(self)
            self._send_html_or_json_error(path, HTTPStatus.NOT_FOUND, "Unknown endpoint")
            return

        secret = getattr(self.server, "webhook_secret", None)
        if secret:
            sig = self.headers.get("X-SG-Signature") or self.headers.get("X-Hub-Signature")
            if not self._verify_signature(sig, secret):
                drain_request_body(self)
                self._send_html_or_json_error(path, HTTPStatus.UNAUTHORIZED, "Invalid signature")
                return

        ctype = (self.headers.get("Content-Type") or "").lower()
        data: Optional[Dict[str, Any]] = None
        err: Optional[str] = None

        if "application/json" in ctype:
            raise RuntimeError("JSON is not supported yet")
        else:
            data, err = read_form_body(self)

        if err is not None:
            drain_request_body(self)
            self._send_html_or_json_error(path, HTTPStatus.BAD_REQUEST, err, echo=data or {})
            return

        # Merge query params into the payload so ?action=... is available for POST too
        query_data_raw = parse_qs(parsed.query, keep_blank_values=True)
        query_data: Dict[str, Any] = {k: (v[0] if len(v) == 1 else v) for k, v in query_data_raw.items()}
        if query_data:
            # URL params take precedence over body for clarity and explicitness
            merged = dict(data or {})
            merged.update(query_data)
            data = merged

        try:
            preview = json.dumps(data or {}, ensure_ascii=False)[:2000]
            logger.debug("AMI payload: %s%s", preview, " …" if len(preview) == 2000 else "")
        except Exception:
            logger.debug("AMI payload received (unprintable)")

        result = self._execute_ami(data)
        if result == -2:
            # Response already sent (parameters form)
            return
        if result == 0:
            content = self._build_html_for_result(data or {}, success=True)
            self._send_html(HTTPStatus.OK, content)
        else:
            self._send_html_or_json_error(path, HTTPStatus.INTERNAL_SERVER_ERROR, "Internal server error")


    def _execute_ami(self, data):
        logger.debug(data)
        action = data.get("action")

        try:
            module = importlib.import_module(f"ami.{action}")

            # Find the first class defined in the module that has a callable main()
            ami_class = None
            for name, obj in module.__dict__.items():
                if isinstance(obj, type) and hasattr(obj, "main") and callable(getattr(obj, "main")):
                    ami_class = obj
                    break

            if not ami_class:
                raise Exception("No class with main() found in ami.%s", action)

            sg = get_sg_session()
            instance = ami_class(sg, data)

            params_fn = getattr(instance, "parameters", None)
            parameters = None
            if callable(params_fn):
                parameters = params_fn()

            # If parameters exist and the form wasn't submitted yet, render the form
            if parameters and not data.get("__form_submitted"):
                self._send_html_with_parameters(action, parameters, data)
                return -2  # signal: response sent

            # If parameters exist and this is a submission, hydrate them from form data
            if parameters and data.get("__form_submitted"):
                for p in parameters:
                    # Use parameter name as the form field key
                    field_key = str(p.name)
                    if field_key in data:
                        p.set(data.get(field_key))

            return instance.main()

        except Exception as e:
            logger.error(e)
            return 1

    def _send_html_with_parameters(self, action: str, parameters: list, original: Dict[str, Any]) -> None:
            # Build a simple form to edit parameters and submit back
            def esc(s: str) -> str:
                return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

            inputs_html = []
            for p in parameters:
                label = esc(str(p.name))
                # Determine current value to show (default if no setter was called yet)
                try:
                    current_val = p.value()
                except Exception:
                    current_val = getattr(p, "default", "")
                if isinstance(current_val, bool):
                    checked = " checked" if current_val else ""
                    inputs_html.append(
                        f'<label style="display:block;margin:8px 0;"><span style="display:inline-block;width:180px;">{label}</span>'
                        f'<input type="checkbox" name="{esc(str(p.name))}" value="true"{checked}></label>'
                    )
                else:
                    inputs_html.append(
                        f'<label style="display:block;margin:8px 0;"><span style="display:inline-block;width:180px;">{label}</span>'
                        f'<input type="text" name="{esc(str(p.name))}" value="{esc(str(current_val))}" '
                        f'style="min-width:320px;padding:6px;border-radius:6px;border:1px solid #555;background:#0b1220;color:#e5e7eb;"></label>'
                    )

            # Keep original context as hidden inputs so we can call main() afterwards
            hidden_inputs = []
            keep_keys = original.keys()
            for k in keep_keys:
                if k == "__form_submitted":
                    continue
                v = original.get(k)
                if v is None:
                    continue
                hidden_inputs.append(f'<input type="hidden" name="{esc(str(k))}" value="{esc(str(v))}">')
            hidden_inputs.append('<input type="hidden" name="__form_submitted" value="1">')
            hidden_inputs.append(f'<input type="hidden" name="action" value="{esc(str(action))}">')

            form_html = f"""
    <!doctype html>
    <html lang="en">
    <head>
    <meta charset="utf-8">
    <title>Parameters</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    </head>
    <body style="margin:0;padding:24px;background:#0f172a;color:#e5e7eb;font:15px/1.5 -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial;">
      <div style="max-width:860px;margin:0 auto;">
        <div style="background:linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));border:1px solid rgba(255,255,255,0.1);border-radius:14px;box-shadow:0 10px 30px rgba(0,0,0,0.35);overflow:hidden;">
          <div style="padding:18px 20px;border-bottom:1px solid rgba(255,255,255,0.08);background:linear-gradient(180deg, rgba(0,0,0,0.2), rgba(0,0,0,0));">
            <h1 style="font-size:18px;margin:0;">Adjust Parameters</h1>
          </div>
          <div style="padding:18px 20px;">
            <form method="post" action="/ami">
              {''.join(hidden_inputs)}
              {''.join(inputs_html)}
              <div style="margin-top:16px;">
                <button type="submit" style="background:#16a34a;color:white;border:none;border-radius:8px;padding:10px 16px;font-weight:600;cursor:pointer;">
                  Send
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </body>
    </html>
    """.strip()

            html_bytes = form_html.encode("utf-8")
            self._send_html(HTTPStatus.OK, html_bytes)

    def _send_html_or_json_error(self, path: str, status: HTTPStatus, message: str,
                                 echo: Optional[Dict[str, Any]] = None) -> None:
        # For AMI endpoints, send HTML by default; otherwise JSON
        if path in ("/", "/ami", "/action") or _wants_html(self):
            html = _render_html_page(
                title=f"{int(status)} {status.phrase}",
                success=False,
                message=message,
                lines=[],
                echo=echo or {},
            )
            self._send_html(status, html)
        else:
            self._send_error_json(status, message)

    def _send_html(self, status: HTTPStatus, html_bytes: bytes) -> None:
        self.send_response(status)
        self._apply_cors()
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html_bytes)))
        self.end_headers()
        self.wfile.write(html_bytes)

    def _send_error_json(self, status: HTTPStatus, message: str) -> None:
        payload = {"error": message, "status": int(status)}
        body = json_dumps(payload)
        self.send_response(status)
        self._apply_cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _verify_signature(self, signature_header: Optional[str], secret: str) -> bool:
        if not signature_header:
            return True
        try:
            algo, _, digest = signature_header.partition("=")
            return bool(algo and digest)
        except Exception:
            return False

    def _build_prototype_response_fields(self, data: Dict[str, Any]) -> Dict[str, Optional[str]]:
        action_name = data.get("action_name") or data.get("action") or data.get("title") or "unknown_action"
        user_login = data.get("user_login") or (data.get("user") or {}).get("name")
        user_id = data.get("user_id") or (data.get("user") or {}).get("id")
        entity_type = data.get("entity_type") or (data.get("entity") or {}).get("type")
        entity_id = data.get("entity_id") or (data.get("entity") or {}).get("id")
        project_name = data.get("project_name") or (data.get("project") or {}).get("name")
        project_id = data.get("project_id") or (data.get("project") or {}).get("id")
        return {
            "action_name": action_name,
            "user": user_login or str(user_id) if (user_login or user_id) else None,
            "entity": f"{entity_type}/{entity_id}" if (entity_type or entity_id) else None,
            "project": project_name or str(project_id) if (project_name or project_id) else None,
        }

    def _build_html_for_result(self, data: Dict[str, Any], success: bool) -> bytes:
        fields = self._build_prototype_response_fields(data)
        lines = [
            f"Action: {fields['action_name']}",
            f"User: {fields['user'] or 'unknown'}",
            f"Entity: {fields['entity'] or '<none>'}",
            f"Project: {fields['project'] or '<none>'}",
        ]
        title = "Action Submitted" if success else "Action Failed"
        message = "Action received and processed." if success else "There was a problem processing your request."
        return _render_html_page(title=title, success=success, message=message, lines=lines, echo=data)


def setup_logging(verbosity: int) -> None:
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def run_server(host: str, port: int, secret: Optional[str]) -> ThreadingHTTPServer:
    class AmiHTTPServer(ThreadingHTTPServer):
        daemon_threads = True
        webhook_secret = secret

    server = AmiHTTPServer((host, port), AmiRequestHandler)
    logger.info("Starting AMI server on http://%s:%d", host, port)
    if secret:
        logger.info("Webhook secret configured")
    return server


def service_main(argv: Optional[list[str]] = None) -> int:
    print("Running AMI server")
    parser = argparse.ArgumentParser(description="Prototype ShotGrid AMI server")
    parser.add_argument("--host", default=os.environ.get("AMI_HOST", "0.0.0.0"), help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("AMI_PORT", "45139")),
                        help="Bind port (default: 45139)")
    parser.add_argument("--secret", default=os.environ.get("SHOTGRID_WEBHOOK_SECRET"),
                        help="Optional shared secret for verifying signatures")
    parser.add_argument("-v", "--verbose", action="count", default=2, help="Increase verbosity (-v, -vv)")

    args = parser.parse_args(argv)
    setup_logging(args.verbose)

    server = run_server(args.host, args.port, args.secret)

    def handle_sig(signum, frame):
        logger.info("Signal %s received, shutting down...", signum)
        threading.Thread(target=server.shutdown, daemon=True).start()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, handle_sig)
        except Exception:
            pass

    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt, shutting down...")
    finally:
        server.server_close()
        logger.info("Server stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(service_main())
