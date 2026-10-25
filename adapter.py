"""Bounded private transport for the normal Hermes gateway.

No model client, API-server recursion, credential disk storage or background service.
The local operator socket is the admission authority; HTTP never chooses identity.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import time

from aiohttp import web
from gateway.config import Platform
from gateway.platforms.base import BasePlatformAdapter, SendResult
from gateway.platforms.event import MessageEvent, ProcessingOutcome
from hermes_constants import get_hermes_home

STATIC = Path(__file__).parent / "web"
TERMINAL = {"answer", "error", "cancelled"}
ID_RE = re.compile(r"^[a-zA-Z0-9_-]{12,100}$")


def check_requirements():
    return importlib.util.find_spec("aiohttp") is not None


class Refused(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


class MiraAdapter(BasePlatformAdapter):
    MAX_MESSAGE_LENGTH = 65536
    SUPPORTS_MESSAGE_EDITING = False
    SUPPORTS_NATIVE_STREAMING = False
    supports_async_delivery = False
    splits_long_messages = True

    def __init__(self, config):
        super().__init__(config, Platform("mira"))
        extra = config.extra
        # This preview intentionally has no remote host/proxy/CORS escape hatch.
        if extra.get("host", "127.0.0.1") != "127.0.0.1":
            raise ValueError("MIRA preview is loopback-only")
        self.port = int(extra.get("port", 8775))
        if not 0 <= self.port <= 65535:
            raise ValueError("Invalid loopback port")
        self.grant_seconds = min(900, max(1, int(extra.get("grant_seconds", 900))))
        self.timeout_seconds = min(300, max(1, int(extra.get("timeout_seconds", 120))))
        self.retention_seconds = 1800
        self.max_records = 64
        self.boot = secrets.token_urlsafe(18)
        self.codes, self.grants, self.principals, self.records = {}, {}, {}, {}
        self.http_runner = self.site = self.operator_server = self.sweeper = None
        self.socket_path = Path(get_hermes_home()) / "mira-operator.sock"
        self.origin = None
        self._attempts = []
        self._http_inflight = self._operator_inflight = 0

    async def connect(self):
        if self.gateway_runner is None or self._authorization_check is None or self._message_handler is None:
            raise RuntimeError("MIRA requires native gateway wiring before connect")
        # Profile-prefix/multiplex routing has not been qualified. Refuse, do not inherit.
        if self._owner_profile or self._shared_listener_profile or getattr(self.gateway_runner.config, "multiplex_profiles", False):
            raise RuntimeError("MIRA preview requires one standalone profile/gateway")
        if getattr(self.gateway_runner.config, "profile_routes", None):
            raise RuntimeError("MIRA preview does not permit cross-profile routes")
        if self.socket_path.exists() or self.socket_path.is_symlink():
            raise RuntimeError("Operator socket exists; reconcile previous process before launch")
        app = web.Application(client_max_size=8192, middlewares=[self.capacity, self.guard])
        app.router.add_route("*", "/{path:.*}", self.route)
        try:
            self.http_runner = web.AppRunner(app, access_log=None, shutdown_timeout=2)
            await self.http_runner.setup()
            self.site = web.TCPSite(self.http_runner, "127.0.0.1", self.port)
            await self.site.start()
            self.port = self.site._server.sockets[0].getsockname()[1]
            self.origin = f"http://127.0.0.1:{self.port}"
            self.operator_server = await asyncio.start_unix_server(self.operator, path=str(self.socket_path), limit=2048)
            os.chmod(self.socket_path, 0o600)
            self.sweeper = asyncio.create_task(self.sweep_loop())
            self._mark_connected(listener_base=self.origin)
            return True
        except BaseException:
            await self.disconnect()
            raise

    async def disconnect(self):
        if self.sweeper:
            self.sweeper.cancel()
            await asyncio.gather(self.sweeper, return_exceptions=True)
            self.sweeper = None
        if self.operator_server:
            self.operator_server.close()
            await self.operator_server.wait_closed()
            self.operator_server = None
            self.socket_path.unlink(missing_ok=True)
        # Stop adapter-owned native tasks, not a second execution engine.
        tasks = list(self._background_tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if self.http_runner:
            await self.http_runner.cleanup()
            self.http_runner = None
        self.codes.clear()
        self.grants.clear()
        self.records.clear()
        self.principals.clear()
        self._mark_disconnected()

    def sweep(self):
        now = time.monotonic()
        for store in (self.codes, self.grants):
            for key, item in list(store.items()):
                if item["expires"] <= now:
                    del store[key]
        for key, row in list(self.records.items()):
            age = now - row["created"]
            if row["state"] == "working" and age > self.timeout_seconds:
                row.update(state="unknown", message="Timed out; execution may still finish. Recover, never resubmit.")
            if age > self.retention_seconds and row["state"] in TERMINAL | {"reserved"}:
                del self.records[key]
        self._attempts = [t for t in self._attempts if now - t < 60]

    async def sweep_loop(self):
        while True:
            await asyncio.sleep(0.5)
            self.sweep()

    def allowed(self, principal, chat):
        return self._is_sender_authorized(principal, "dm", chat) is True

    def new_pairing(self, principal):
        self.sweep()
        if not isinstance(principal, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", principal):
            raise Refused(400, "Invalid principal")
        existing = self.principals.get(principal)
        chat = existing["chat"] if existing else "mira-" + secrets.token_hex(16)
        if not self.allowed(principal, chat):
            raise Refused(403, "Principal not authorized by native gateway")
        if not existing:
            if len(self.principals) >= 16:
                raise Refused(429, "Principal capacity reached; operator restart required")
            self.principals[principal] = {"chat": chat}
        # One code per principal; explicit local re-pair revokes old grant immediately.
        self.revoke(principal)
        code = secrets.token_urlsafe(24)
        self.codes[self.digest(code)] = {"principal": principal, "expires": time.monotonic() + 60}
        return {"code": code, "expires_in": 60, "origin": self.origin}

    def revoke(self, principal):
        for store in (self.codes, self.grants):
            for key, item in list(store.items()):
                if item["principal"] == principal:
                    del store[key]

    @staticmethod
    def digest(value):
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    async def operator(self, reader, writer):
        if self._operator_inflight >= 8:
            writer.close()
            await writer.wait_closed()
            return
        self._operator_inflight += 1
        try:
            await self._operator_command(reader, writer)
        finally:
            self._operator_inflight -= 1

    async def _operator_command(self, reader, writer):
        # OS-local operator authority, socket mode 0600. No code/token file or logging.
        try:
            raw = await asyncio.wait_for(reader.readline(), 2)
            data = json.loads(raw)
            if not isinstance(data, dict) or set(data) != {"action", "principal"}:
                raise Refused(400, "Invalid operator command")
            if data["action"] == "pair":
                result = self.new_pairing(data["principal"])
            elif data["action"] == "revoke":
                self.revoke(data["principal"])
                result = {"revoked": True}
            else:
                raise Refused(400, "Unsupported operator command")
        except Exception:
            result = {"error": "Operator command refused"}
        writer.write(json.dumps(result).encode() + b"\n")
        try:
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    @web.middleware
    async def capacity(self, request, handler):
        if self._http_inflight >= 32:
            return web.json_response({"error": "Ingress capacity reached"}, status=429,
                                     headers={"Cache-Control": "no-store"})
        self._http_inflight += 1
        try:
            return await handler(request)
        finally:
            self._http_inflight -= 1

    @web.middleware
    async def guard(self, request, handler):
        try:
            if request.host != f"127.0.0.1:{self.port}":
                raise Refused(403, "Host refused")
            if request.query_string:
                raise Refused(400, "Query parameters not supported")
            if request.path.startswith("/api/"):
                origin_ok = request.headers.get("Origin") == self.origin or (
                    request.method == "GET" and "Origin" not in request.headers
                    and request.headers.get("Sec-Fetch-Site") == "same-origin")
                if not origin_ok or request.headers.get("X-Mira-Client") != "1":
                    raise Refused(403, "Origin refused")
                if request.headers.get("Sec-Fetch-Site", "same-origin") != "same-origin":
                    raise Refused(403, "Cross-site request refused")
                if request.method == "POST" and request.content_type != "application/json":
                    raise Refused(415, "JSON required")
            response = await handler(request)
        except Refused as e:
            response = web.json_response({"error": e.message}, status=e.status)
        except (web.HTTPRequestEntityTooLarge, UnicodeError):
            response = web.json_response({"error": "Payload too large or invalid encoding"}, status=413)
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            response = web.json_response({"error": "Invalid request"}, status=400)
        except Exception:
            response = web.json_response({"error": "Backend unavailable; outcome may be unknown"}, status=503)
        response.headers.update({"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"})
        return response

    async def body(self, request, keys):
        data = await asyncio.wait_for(request.json(), 3)
        if not isinstance(data, dict) or set(data) != set(keys):
            raise Refused(400, "Invalid fields; identity and routing are server-owned")
        return data

    def authenticate(self, request):
        self.sweep()
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or len(auth) > 160:
            raise Refused(401, "Pairing required")
        grant = self.grants.get(self.digest(auth[7:]))
        if grant is None:
            raise Refused(401, "Grant expired or revoked; foreground re-pair required")
        principal = grant["principal"]
        if not self.allowed(principal, self.principals[principal]["chat"]):
            self.revoke(principal)
            raise Refused(403, "Native gateway authorization denied")
        return principal

    def view(self, row):
        if row is None:
            return {"state": "unknown", "message": "Unknown or expired request; do not resubmit. Reconcile with operator."}
        return {k: row[k] for k in ("request_id", "state", "message", "answer") if k in row}

    async def route(self, request):
        path = request.path
        assets = {"/": "index.html", **{"/"+p: p for p in ("app.js", "companion.js", "mira-binding.js", "style.css")}}
        if request.method == "GET" and path in assets:
            return web.FileResponse(STATIC / assets[path])
        if path == "/api/pair" and request.method == "POST":
            self.sweep()
            if len(self._attempts) >= 10:
                raise Refused(429, "Pairing rate limit; wait one minute")
            self._attempts.append(time.monotonic())
            data = await self.body(request, {"code"})
            if not isinstance(data["code"], str) or len(data["code"]) > 128:
                raise Refused(400, "Invalid code")
            entry = self.codes.pop(self.digest(data["code"]), None)
            if not entry:
                raise Refused(401, "Pairing code expired, used or invalid")
            principal = entry["principal"]
            if not self.allowed(principal, self.principals[principal]["chat"]):
                raise Refused(403, "Native gateway authorization denied")
            token = secrets.token_urlsafe(32)
            self.grants[self.digest(token)] = {"principal": principal, "expires": time.monotonic() + self.grant_seconds}
            return web.json_response({"token": token, "expires_in": self.grant_seconds, "boot": self.boot})
        if not path.startswith("/api/"):
            raise Refused(404, "Not found")
        principal = self.authenticate(request)
        if path == "/api/current" and request.method == "GET":
            rows = [r for r in self.records.values() if r["principal"] == principal]
            return web.json_response({"boot": self.boot, "current": self.view(rows[-1]) if rows else None})
        if path == "/api/revoke" and request.method == "POST":
            await self.body(request, set())
            self.revoke(principal)
            return web.json_response({"revoked": True})
        if path == "/api/ticket" and request.method == "POST":
            await self.body(request, set())
            if len(self.records) >= self.max_records:
                raise Refused(429, "Request retention capacity reached")
            if any(r["principal"] == principal and r["state"] in {"working", "unknown", "reserved"} for r in self.records.values()):
                raise Refused(409, "Outstanding request; recover first")
            ident = self.boot + "_" + secrets.token_urlsafe(18)
            self.records[ident] = {"request_id": ident, "principal": principal, "created": time.monotonic(), "state": "reserved"}
            return web.json_response({"request_id": ident})
        if path == "/api/requests" and request.method == "POST":
            data = await self.body(request, {"request_id", "text"})
            ident, text = data["request_id"], data["text"]
            if not isinstance(text, str) or not text.strip() or len(text.encode("utf-8")) > 4096:
                raise Refused(400, "Text must be 1-4096 UTF-8 bytes")
            if not isinstance(ident, str) or not ID_RE.fullmatch(ident):
                raise Refused(400, "Invalid request ID")
            row = self.records.get(ident)
            if not row or row["principal"] != principal:
                raise Refused(409, "Unknown request ticket; never replay after restart/expiry")
            digest = self.digest(text)
            if row.get("digest"):
                if not hmac.compare_digest(row["digest"], digest):
                    raise Refused(409, "Request ID/body conflict")
                return web.json_response(self.view(row))
            if row["state"] != "reserved":
                raise Refused(409, "Ticket no longer admits a request")
            chat = self.principals[principal]["chat"]
            source = self.build_source(chat_id=chat, user_id=principal, chat_type="dm", message_id=ident)
            if source.profile_route_rejected or source.profile not in (None, self._owner_profile):
                raise Refused(403, "Profile route refused")
            event = MessageEvent(text=text, source=source, user_id=principal, message_id=ident,
                                 allow_gateway_control=False, reply_expected=True)
            row.update(digest=digest, state="working", chat=chat, event=event, message="Working; final answer only.")
            try:
                await self.handle_message(event)
                if not event._gateway_accepted:
                    row.update(state="error", message="Gateway did not admit this request.")
            except Exception:
                row.update(state="unknown", message="Gateway admission outcome unknown; do not resubmit.")
            return web.json_response(self.view(row))
        match = re.fullmatch(r"/api/requests/([A-Za-z0-9_-]{12,100})(/recover|/stop)?", path)
        if match:
            ident, action = match.groups()
            if (action is None and request.method != "GET") or (action and request.method != "POST"):
                raise Refused(405, "Method refused")
            if action:
                await self.body(request, set())
            row = self.records.get(ident)
            if row and row["principal"] != principal:
                row = None
            if action == "/stop" and row and row["state"] == "reserved":
                row.update(state="cancelled", message="Unused ticket cancelled; no request was submitted.")
            if action == "/stop" and row and row["state"] in {"working", "unknown"}:
                event = row["event"]
                # A single server-generated native /stop. Client text cannot invoke commands.
                if not row.get("stop_requested"):
                    row["stop_requested"] = True
                    stop = MessageEvent(text="/stop", source=event.source,
                        message_id="stop-"+ident, allow_gateway_control=True)
                    await self.handle_message(stop)
                row["message"] = "Stop requested; not a rollback. Waiting for confirmed outcome."
            return web.json_response(self.view(row))
        raise Refused(404, "Not found")

    async def send(self, chat_id, content, reply_to=None, metadata=None, **kwargs):
        # Only request-correlated, native final delivery can cross the transport.
        # No commentary/reasoning/tools/proactive notices or raw exception fallback.
        row = self.records.get(reply_to)
        if not row or row.get("chat") != chat_id or row["state"] not in {"working", "unknown"}:
            return SendResult(success=False, error="Uncorrelated delivery refused")
        if not metadata or metadata.get("notify") is not True or metadata.get("is_approval_prompt"):
            return SendResult(success=False, error="Non-final delivery refused")
        if row.get("approval_denied"):
            return SendResult(success=False, error="Approval unavailable")
        text = re.sub(r"<(think|analysis|reasoning)\b[^>]*>.*?(</\1>|$)", "", str(content), flags=re.S | re.I)
        # Defensive common credential shapes, not a universal DLP promise.
        text = re.sub(r"(?i)\b(?:bearer\s+|sk-)[A-Za-z0-9_.-]{12,}", "[redacted]", text)
        if len(text.encode("utf-8")) > 65536:
            row.update(state="error", message="Final answer exceeds 65536-byte host limit.")
            return SendResult(success=False, error="Answer too large")
        row["answer"] = text
        return SendResult(success=True, message_id=reply_to)

    async def on_processing_complete(self, event, outcome):
        row = self.records.get(event.message_id)
        if not row:
            return
        if row.get("approval_denied"):
            row.update(state="error", message="Approval unavailable; request denied.")
            row.pop("answer", None)
        elif outcome == ProcessingOutcome.CANCELLED or row.get("stop_requested"):
            row.update(state="cancelled", message="Gateway processing ended after stop; prior effects are not rolled back.")
            row.pop("answer", None)
        elif outcome == ProcessingOutcome.SUCCESS and "answer" in row:
            row.update(state="answer", message="Final answer")
        else:
            row.update(state="error", message="Gateway failed or returned no deliverable final answer.")
            row.pop("answer", None)
        row.pop("event", None)

    async def _send_exec_approval_prompt(self, prompt):
        from tools.approval import resolve_gateway_approval
        rows = [r for r in self.records.values() if r.get("chat") == prompt.chat_id and r["state"] in {"working", "unknown"}]
        for row in rows:
            row["approval_denied"] = True
        resolve_gateway_approval(prompt.session_key, "deny", resolve_all=True)
        # Success means denial was handled, not an approval button was offered.
        return SendResult(success=True, message_id="approval-denied")

    async def send_typing(self, chat_id, **kwargs):
        return None

    def format_tool_event(self, event, **kwargs):
        return None

    async def send_image(self, chat_id, image_url, caption=None, **kwargs):
        return SendResult(success=False, error="Media delivery not supported")

    async def get_chat_info(self, chat_id):
        return {"name": "MIRA private conversation", "type": "dm", "chat_id": chat_id}
