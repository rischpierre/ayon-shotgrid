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
from string import Template

logger = logging.getLogger("proto-ami-server")


# Templates directory and loader
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")


def _load_template(name: str) -> str:
    path = os.path.join(TEMPLATES_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


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
    # Render via external HTML template
    badge_color = "#16a34a" if success else "#dc2626"
    border_color = "#22c55e" if success else "#f87171"
    badge_label = "Success" if success else "Error"
    footer_text = "ShotGrid AMI Prototype • All good." if success else "ShotGrid AMI Prototype • Please review and retry."
    safe_pre = json.dumps(echo, ensure_ascii=False, indent=2)
    items_html = "".join(f"<li>{line}</li>" for line in lines)

    template_text = _load_template("page.html")
    html = Template(template_text).safe_substitute(
        {
            "title": title,
            "badge_color": badge_color,
            "border_color": border_color,
            "badge_label": badge_label,
            "message": message,
            "items_html": items_html,
            "safe_pre": safe_pre,
            "footer_text": footer_text,
        }
    )
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
        # Normalize action: ShotGrid may submit duplicate 'action' fields leading to a list
        if isinstance(action, list):
            if not action:
                raise Exception("No action specified")
            logger.debug("Multiple action values received %s; using first '%s'", action, action[0])
            action = action[0]
        if not isinstance(action, str) or not action.strip():
            raise Exception("Invalid action value")

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
                if k in ("__form_submitted", "action"):
                    continue
                v = original.get(k)
                if v is None:
                    continue
                hidden_inputs.append(f'<input type="hidden" name="{esc(str(k))}" value="{esc(str(v))}">')
            hidden_inputs.append('<input type="hidden" name="__form_submitted" value="1">')
            hidden_inputs.append(f'<input type="hidden" name="action" value="{esc(str(action))}">')

            # Render using external template
            template_text = _load_template("parameters.html")
            html = Template(template_text).safe_substitute(
                {
                    "title": "Parameters",
                    "heading": "Adjust Parameters",
                    "action_url": "/ami",
                    "hidden_inputs": "".join(hidden_inputs),
                    "inputs_html": "".join(inputs_html),
                    "submit_label": "Send",
                }
            )

            self._send_html(HTTPStatus.OK, html.encode("utf-8"))

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
        if isinstance(action_name, list):
            action_name = action_name[0] if action_name else "unknown_action"
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
