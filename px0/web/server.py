"""HTTP Server for px0 web interface."""

import os
import signal
import socketserver
import threading
import urllib.parse
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
import json
from dataclasses import asdict

from px0 import (
    approvals as approvals_mod,
    authoring,
    daemon as daemon_mod,
    inbox as inbox_mod,
    paths,
    runner,
    runs as runs_mod,
    ui,
    workflow as workflow_mod,
)
from px0.web import views


class WebUIHandler(SimpleHTTPRequestHandler):
    home: Path
    config: dict

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        # Static assets
        if path.startswith("/static/"):
            asset_name = path[len("/static/"):]
            static_dir = Path(__file__).parent / "static"
            asset_path = static_dir / asset_name
            if asset_path.exists() and asset_path.is_file():
                content_type = "text/plain"
                if asset_name.endswith(".css"):
                    content_type = "text/css"
                elif asset_name.endswith(".js"):
                    content_type = "application/javascript"
                data = asset_path.read_bytes()
                self._send_response(HTTPStatus.OK, data, content_type)
                return
            else:
                self._send_response(HTTPStatus.NOT_FOUND, b"Asset not found", "text/plain")
                return

        # =========================================================================
        # HTMX Fragment Endpoints (Dedicated UI Partial Rendering)
        # =========================================================================

        # Daemon polling badge
        if path == "/htmx/daemon/badge":
            d_status = daemon_mod.status(self.home, self.config)
            html_out = views.render_daemon_badge(d_status)
            self._send_response(HTTPStatus.OK, html_out.encode(), "text/html")
            return

        # Needs-action polling badge
        if path == "/htmx/needs-action/badge":
            html_out = views.render_needs_action_badge(self.home, self.config)
            self._send_response(HTTPStatus.OK, html_out.encode(), "text/html")
            return

        # Deterministic per-app live data portal section
        if path.startswith("/htmx/portal/"):
            app = path[len("/htmx/portal/"):]
            if app not in dict(views.APP_TABS):
                self._send_response(HTTPStatus.NOT_FOUND, b"unknown app", "text/plain")
                return
            from px0 import portal as portal_mod
            text, updated_at = portal_mod.load_or_refresh(app, self.home, self.config)
            html_out = views.render_portal_section(app, text, updated_at)
            self._send_response(HTTPStatus.OK, html_out.encode(), "text/html")
            return

        # HTMX partial view updates
        if path == "/htmx/views/dashboard":
            html_out = views.render_dashboard(self.home, self.config)
            self._send_response(HTTPStatus.OK, html_out.encode(), "text/html")
            return
        elif path == "/htmx/views/needs-action":
            html_out = views.render_needs_action(self.home, self.config)
            self._send_response(HTTPStatus.OK, html_out.encode(), "text/html")
            return
        elif path == "/htmx/views/workflows":
            html_out = views.render_workflows_list(self.home, self.config)
            self._send_response(HTTPStatus.OK, html_out.encode(), "text/html")
            return
        elif path == "/htmx/views/schedules":
            html_out = views.render_schedules_list(self.home, self.config)
            self._send_response(HTTPStatus.OK, html_out.encode(), "text/html")
            return
        elif path == "/htmx/views/runs":
            html_out = views.render_runs_list(self.config)
            self._send_response(HTTPStatus.OK, html_out.encode(), "text/html")
            return
        elif path == "/htmx/views/daemon":
            html_out = views.render_daemon_view(self.home, self.config)
            self._send_response(HTTPStatus.OK, html_out.encode(), "text/html")
            return

        # HTMX Modal endpoints
        if path.startswith("/htmx/workflows/") and path.endswith("/run-modal"):
            wf_id = path[len("/htmx/workflows/"):-len("/run-modal")]
            try:
                wf = workflow_mod.load(self.home, wf_id)
                html_out = views.render_run_modal(wf)
                self._send_response(HTTPStatus.OK, html_out.encode(), "text/html")
            except Exception as e:
                self._send_response(HTTPStatus.NOT_FOUND, str(e).encode(), "text/plain")
            return

        if path.startswith("/htmx/workflows/"):
            wf_id = path[len("/htmx/workflows/"):]
            try:
                wf = workflow_mod.load(self.home, wf_id)
                html_out = views.render_workflow_detail_modal(wf)
                self._send_response(HTTPStatus.OK, html_out.encode(), "text/html")
            except Exception as e:
                self._send_response(HTTPStatus.NOT_FOUND, str(e).encode(), "text/plain")
            return

        if path.startswith("/htmx/schedules/") and path.endswith("/edit"):
            wf_id = path[len("/htmx/schedules/"):-len("/edit")]
            try:
                wf = workflow_mod.load(self.home, wf_id)
                html_out = views.render_schedule_edit_modal(wf)
                self._send_response(HTTPStatus.OK, html_out.encode(), "text/html")
            except Exception as e:
                self._send_response(HTTPStatus.NOT_FOUND, str(e).encode(), "text/plain")
            return

        if path.startswith("/htmx/runs/"):
            run_id = path[len("/htmx/runs/"):]
            html_out = views.render_run_detail_modal(self.config, run_id)
            self._send_response(HTTPStatus.OK, html_out.encode(), "text/html")
            return

        if path.startswith("/htmx/inbox/"):
            entry_id = path[len("/htmx/inbox/"):]
            html_out = views.render_inbox_entry_detail_modal(self.home, self.config, entry_id)
            self._send_response(HTTPStatus.OK, html_out.encode(), "text/html")
            return

        # =========================================================================
        # REST / JSON API Endpoints (Data & Integrations)
        # =========================================================================

        # Daemon status
        if path in ("/api/daemon/status", "/api/daemon"):
            d_status = daemon_mod.status(self.home, self.config)
            self._send_json(HTTPStatus.OK, d_status)
            return

        # Needs-action summary counts
        if path == "/api/needs-action/summary":
            pending_approvals = approvals_mod.pending_count(self.home, self.config)
            unread_entries = len(inbox_mod.listing(self.home, status=inbox_mod.UNREAD, attention=inbox_mod.NEEDS_ACTION))
            self._send_json(HTTPStatus.OK, {
                "pending_approvals": pending_approvals,
                "unread_needs_action": unread_entries,
                "total": pending_approvals + unread_entries,
            })
            return

        # Portal JSON data
        if path.startswith("/api/portal/"):
            app = path[len("/api/portal/"):]
            if app not in dict(views.APP_TABS):
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "unknown app"})
                return
            from px0 import portal as portal_mod
            text, updated_at = portal_mod.load_or_refresh(app, self.home, self.config)
            self._send_json(HTTPStatus.OK, {
                "app": app,
                "content": text,
                "updated_at": updated_at,
            })
            return

        # Workflows JSON list & details
        if path == "/api/workflows":
            all_wfs = workflow_mod.load_all(self.home)
            items = []
            for wf_id, wf in sorted(all_wfs.items()):
                items.append({
                    "id": wf.id,
                    "enabled": wf.enabled,
                    "description": wf.description,
                    "request": wf.request,
                    "trigger": wf.trigger,
                    "tools": wf.tools,
                })
            self._send_json(HTTPStatus.OK, {"workflows": items})
            return

        if path.startswith("/api/workflows/"):
            wf_id = path[len("/api/workflows/"):]
            try:
                wf = workflow_mod.load(self.home, wf_id)
                self._send_json(HTTPStatus.OK, {
                    "id": wf.id,
                    "enabled": wf.enabled,
                    "description": wf.description,
                    "request": wf.request,
                    "trigger": wf.trigger,
                    "tools": wf.tools,
                    "body": wf.body,
                    "inputs": [asdict(inp) for inp in wf.inputs],
                    "vars": wf.vars,
                })
            except Exception as e:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(e)})
            return

        # Schedules JSON list
        if path == "/api/schedules":
            all_wfs = workflow_mod.load_all(self.home)
            state = daemon_mod.load_schedule_state(self.home)
            items = []
            for wf_id, wf in sorted(all_wfs.items()):
                schedule = (wf.trigger or {}).get("schedule")
                if schedule:
                    items.append({
                        "workflow_id": wf.id,
                        "schedule": schedule,
                        "enabled": wf.enabled,
                        "last_fire": state.get(wf_id),
                    })
            self._send_json(HTTPStatus.OK, {"schedules": items})
            return

        # Runs JSON list & details
        if path == "/api/runs":
            records = runs_mod.list_records(self.config)[:100]
            self._send_json(HTTPStatus.OK, {"runs": records})
            return

        if path.startswith("/api/runs/"):
            run_id = path[len("/api/runs/"):]
            try:
                record = runs_mod.read_record(self.config, run_id)
                events = runs_mod.read_events(self.config, run_id)
                self._send_json(HTTPStatus.OK, {"record": record, "events": events})
            except Exception as e:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(e)})
            return

        # Approvals JSON list
        if path == "/api/approvals":
            pending = approvals_mod.listing(self.home, self.config, status=approvals_mod.PENDING)
            self._send_json(HTTPStatus.OK, {"approvals": pending})
            return

        if path.startswith("/api/approvals/"):
            approval_id = path[len("/api/approvals/"):]
            try:
                approval = approvals_mod.read(self.home, approval_id)
                self._send_json(HTTPStatus.OK, approval)
            except Exception as e:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(e)})
            return

        # Inbox JSON list & details
        if path == "/api/inbox":
            entries = inbox_mod.listing(self.home)
            self._send_json(HTTPStatus.OK, {"inbox": entries})
            return

        if path.startswith("/api/inbox/"):
            entry_id = path[len("/api/inbox/"):]
            try:
                entry = inbox_mod.read_entry(self.home, entry_id)
                body = inbox_mod.body(self.home, self.config, entry)
                res = dict(entry)
                res["body"] = body
                self._send_json(HTTPStatus.OK, res)
            except Exception as e:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(e)})
            return

        # Full page views (browser navigation / direct URL access)
        d_status = daemon_mod.status(self.home, self.config)
        if path in ("", "/", "/needs-action"):
            content = views.render_needs_action(self.home, self.config)
            full_html = views.page_shell(content, active_tab="needs-action", daemon_status=d_status,
                                         home=self.home, config=self.config)
            self._send_response(HTTPStatus.OK, full_html.encode(), "text/html")
            return
        elif path == "/stats":
            content = views.render_dashboard(self.home, self.config)
            full_html = views.page_shell(content, active_tab="stats", daemon_status=d_status,
                                         home=self.home, config=self.config)
            self._send_response(HTTPStatus.OK, full_html.encode(), "text/html")
            return
        elif path == "/workflows":
            content = views.render_workflows_list(self.home, self.config)
            full_html = views.page_shell(content, active_tab="workflows", daemon_status=d_status,
                                         home=self.home, config=self.config)
            self._send_response(HTTPStatus.OK, full_html.encode(), "text/html")
            return
        elif path == "/schedules":
            content = views.render_schedules_list(self.home, self.config)
            full_html = views.page_shell(content, active_tab="schedules", daemon_status=d_status,
                                         home=self.home, config=self.config)
            self._send_response(HTTPStatus.OK, full_html.encode(), "text/html")
            return
        elif path == "/runs":
            content = views.render_runs_list(self.config)
            full_html = views.page_shell(content, active_tab="runs", daemon_status=d_status,
                                         home=self.home, config=self.config)
            self._send_response(HTTPStatus.OK, full_html.encode(), "text/html")
            return
        elif path == "/daemon":
            content = views.render_daemon_view(self.home, self.config)
            full_html = views.page_shell(content, active_tab="daemon", daemon_status=d_status,
                                         home=self.home, config=self.config)
            self._send_response(HTTPStatus.OK, full_html.encode(), "text/html")
            return

        self._send_response(HTTPStatus.NOT_FOUND, b"Page not found", "text/plain")

    def do_POST(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else ""
        form_data = urllib.parse.parse_qs(body)

        # =========================================================================
        # HTMX Mutation Endpoints (Return HTML fragments or triggers)
        # =========================================================================

        # Force a fresh deterministic-portal fetch for one app tab
        if path.startswith("/htmx/portal/") and path.endswith("/refresh"):
            app = path[len("/htmx/portal/"):-len("/refresh")]
            if app not in dict(views.APP_TABS):
                self._send_response(HTTPStatus.NOT_FOUND, b"unknown app", "text/plain")
                return
            try:
                from px0 import portal as portal_mod
                text = portal_mod.refresh(app, self.home, self.config)
                updated_at = portal_mod.portal_path(self.home, app).stat().st_mtime
                html_out = views.render_portal_section(app, text, updated_at)
                self._send_response(HTTPStatus.OK, html_out.encode(), "text/html")
            except Exception as e:
                self._send_response(HTTPStatus.INTERNAL_SERVER_ERROR, str(e).encode(), "text/plain")
            return

        # Toggle enable/disable for a workflow
        if path.startswith("/htmx/workflows/") and path.endswith("/toggle"):
            wf_id = path[len("/htmx/workflows/"):-len("/toggle")]
            try:
                wf = workflow_mod.load(self.home, wf_id)
                new_state = not wf.enabled
                text = wf.path.read_text()
                updated_text = authoring.set_frontmatter_key(text, "enabled", new_state)
                authoring.write_file(
                    self.home,
                    wf.path,
                    updated_text,
                    evidence=f"workflow {wf.id} {'enabled' if new_state else 'disabled'} via web ui"
                )
                daemon_mod.restart_if_running(self.home, self.config)
                
                # Check if caller was on workflows view or schedules view
                referer = self.headers.get("Referer", "")
                if "schedules" in referer:
                    html_out = views.render_schedules_list(self.home, self.config)
                else:
                    wf_updated = workflow_mod.load(self.home, wf_id)
                    html_out = views.render_workflow_row(wf_updated)

                self._send_response(HTTPStatus.OK, html_out.encode(), "text/html")
            except Exception as e:
                self._send_response(HTTPStatus.INTERNAL_SERVER_ERROR, str(e).encode(), "text/plain")
            return

        # Update schedule for a workflow
        if path.startswith("/htmx/schedules/") and path.endswith("/update"):
            wf_id = path[len("/htmx/schedules/"):-len("/update")]
            new_schedule = form_data.get("schedule", [""])[0].strip()
            try:
                wf = workflow_mod.load(self.home, wf_id)
                text = wf.path.read_text()
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    import re
                    front, body = parts[1], parts[2]
                    if re.search(r"^\s*schedule\s*:", front, flags=re.MULTILINE):
                        front = re.sub(r"(^\s*schedule\s*:).*$", rf'\g<1> "{new_schedule}"', front, flags=re.MULTILINE)
                    elif re.search(r"^\s*trigger\s*:", front, flags=re.MULTILINE):
                        front = re.sub(r"(^\s*trigger\s*:.*$)", rf'\g<1>\n  schedule: "{new_schedule}"', front, flags=re.MULTILINE)
                    else:
                        front = front + f'\ntrigger:\n  schedule: "{new_schedule}"\n'
                    updated_text = "---" + front + "---" + body
                else:
                    updated_text = text

                authoring.write_file(
                    self.home,
                    wf.path,
                    updated_text,
                    evidence=f"schedule updated to '{new_schedule}' for {wf.id} via web ui"
                )
                daemon_mod.restart_if_running(self.home, self.config)

                # Re-render schedules list and clear modal
                html_out = views.render_schedules_list(self.home, self.config)
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html")
                self.send_header("HX-Trigger", "closeModalTrigger")
                html_out += "<script>closeModal();</script>"
                self.send_header("Content-Length", str(len(html_out.encode())))
                self.end_headers()
                self.wfile.write(html_out.encode())
            except Exception as e:
                self._send_response(HTTPStatus.INTERNAL_SERVER_ERROR, str(e).encode(), "text/plain")
            return

        # Trigger workflow run
        if path.startswith("/htmx/workflows/") and path.endswith("/trigger"):
            wf_id = path[len("/htmx/workflows/"):-len("/trigger")]
            try:
                cli_inputs = {}
                for k, v in form_data.items():
                    if k.startswith("var_") and v:
                        cli_inputs[k[len("var_"):]] = v[0]

                # Run detached in a background thread so UI stays responsive
                def _bg_run():
                    try:
                        runner.run(
                            self.home,
                            self.config,
                            wf_id,
                            trigger="manual",
                            cli_inputs=cli_inputs,
                        )
                    except Exception:
                        pass

                t = threading.Thread(target=_bg_run, daemon=True)
                t.start()

                resp_html = f'''
                <div style="background: var(--success-bg); border: 1px solid rgba(113, 176, 113, 0.4); padding: 12px; border-radius: 4px; color: var(--success);">
                  Run initiated successfully in the background! Check <a href="/runs" hx-get="/htmx/views/runs" hx-target="#main-view" onclick="closeModal()" style="color: var(--accent); text-decoration: underline;">Runs</a> for results.
                </div>
                '''
                self._send_response(HTTPStatus.OK, resp_html.encode(), "text/html")
            except Exception as e:
                err_html = f'''
                <div style="background: var(--danger-bg); border: 1px solid rgba(224, 108, 117, 0.4); padding: 12px; border-radius: 4px; color: var(--danger);">
                  Failed to start run: {views._escape(str(e))}
                </div>
                '''
                self._send_response(HTTPStatus.OK, err_html.encode(), "text/html")
            return

        # Approve or reject a queued write, inline from the needs-action view
        if path.startswith("/htmx/approvals/") and path.endswith("/approve"):
            approval_id = path[len("/htmx/approvals/"):-len("/approve")]
            try:
                result = approvals_mod.approve(self.home, self.config, approval_id)
                if result.get("status") == approvals_mod.FAILED:
                    body = (f'<div style="color: var(--danger);">the tool call failed: '
                            f'{views._escape(result.get("detail", ""))}</div>').encode()
                else:
                    body = b""
                self._send_response(HTTPStatus.OK, body, "text/html")
            except approvals_mod.ApprovalError as e:
                self._send_response(HTTPStatus.OK,
                                    f'<div style="color: var(--danger);">{views._escape(str(e))}</div>'.encode(),
                                    "text/html")
            return

        if path.startswith("/htmx/approvals/") and path.endswith("/reject"):
            approval_id = path[len("/htmx/approvals/"):-len("/reject")]
            reason = form_data.get("reason", [""])[0]
            try:
                approvals_mod.reject(self.home, self.config, approval_id, reason=reason)
                self._send_response(HTTPStatus.OK, b"", "text/html")
            except approvals_mod.ApprovalError as e:
                self._send_response(HTTPStatus.OK,
                                    f'<div style="color: var(--danger);">{views._escape(str(e))}</div>'.encode(),
                                    "text/html")
            return

        # Mark/archive an inbox entry from the needs-action view
        if path.startswith("/htmx/inbox/") and path.endswith("/mark"):
            entry_id = path[len("/htmx/inbox/"):-len("/mark")]
            new_status = form_data.get("status", [inbox_mod.READ])[0]
            try:
                inbox_mod.mark(self.home, entry_id, new_status)
                self._send_response(HTTPStatus.OK, b"", "text/html")
            except inbox_mod.InboxError as e:
                self._send_response(HTTPStatus.OK,
                                    f'<div style="color: var(--danger);">{views._escape(str(e))}</div>'.encode(),
                                    "text/html")
            return

        # Daemon actions: start, stop, tick
        if path == "/htmx/daemon/action":
            act = query.get("act", [""])[0]
            if act == "tick":
                try:
                    state = daemon_mod.load_schedule_state(self.home)
                    daemon_mod.tick(self.home, self.config, state)
                    msg = '<div style="margin-top: 10px; color: var(--success);">Schedule tick completed successfully.</div>'
                    self._send_response(HTTPStatus.OK, msg.encode(), "text/html")
                except Exception as e:
                    msg = f'<div style="margin-top: 10px; color: var(--danger);">Tick error: {views._escape(str(e))}</div>'
                    self._send_response(HTTPStatus.OK, msg.encode(), "text/html")
                return
            elif act == "start":
                header_scope = query.get("scope", [""])[0] == "header"
                try:
                    status = daemon_mod.status(self.home, self.config)
                    spawn_failed = False
                    if not status.get("alive"):
                        try:
                            daemon_mod.spawn_serve(self.home)
                        except OSError:
                            spawn_failed = True
                        import time; time.sleep(0.5)
                        status = daemon_mod.status(self.home, self.config)

                    if header_scope:
                        html_out = views.render_daemon_badge(
                            status, start_failed=spawn_failed or not status.get("alive"))
                    else:
                        html_out = views.render_daemon_view(self.home, self.config)
                    self._send_response(HTTPStatus.OK, html_out.encode(), "text/html")
                except Exception as e:
                    self._send_response(HTTPStatus.INTERNAL_SERVER_ERROR, str(e).encode(), "text/plain")
                return
            elif act == "stop":
                try:
                    status = daemon_mod.status(self.home, self.config)
                    if status.get("alive") and status.get("pid"):
                        os.kill(status["pid"], signal.SIGTERM)
                    import time; time.sleep(0.5)
                    html_out = views.render_daemon_view(self.home, self.config)
                    self._send_response(HTTPStatus.OK, html_out.encode(), "text/html")
                except Exception as e:
                    self._send_response(HTTPStatus.INTERNAL_SERVER_ERROR, str(e).encode(), "text/plain")
                return

        # =========================================================================
        # REST / JSON API Mutation Endpoints (Return JSON data)
        # =========================================================================

        # JSON payload parsing helper
        json_payload = {}
        if self.headers.get("Content-Type", "").startswith("application/json") and body:
            try:
                json_payload = json.loads(body)
            except Exception:
                json_payload = {}

        # Refresh portal via JSON API
        if path.startswith("/api/portal/") and path.endswith("/refresh"):
            app = path[len("/api/portal/"):-len("/refresh")]
            if app not in dict(views.APP_TABS):
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "unknown app"})
                return
            try:
                from px0 import portal as portal_mod
                text = portal_mod.refresh(app, self.home, self.config)
                updated_at = portal_mod.portal_path(self.home, app).stat().st_mtime
                self._send_json(HTTPStatus.OK, {
                    "app": app,
                    "content": text,
                    "updated_at": updated_at,
                })
            except Exception as e:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(e)})
            return

        # Toggle workflow via JSON API
        if path.startswith("/api/workflows/") and path.endswith("/toggle"):
            wf_id = path[len("/api/workflows/"):-len("/toggle")]
            try:
                wf = workflow_mod.load(self.home, wf_id)
                # Allow specifying target enabled state in json_payload or form_data, or toggle if omitted
                if "enabled" in json_payload:
                    new_state = bool(json_payload["enabled"])
                elif "enabled" in form_data:
                    new_state = form_data["enabled"][0].lower() in ("true", "1", "yes")
                else:
                    new_state = not wf.enabled

                text = wf.path.read_text()
                updated_text = authoring.set_frontmatter_key(text, "enabled", new_state)
                authoring.write_file(
                    self.home,
                    wf.path,
                    updated_text,
                    evidence=f"workflow {wf.id} {'enabled' if new_state else 'disabled'} via api"
                )
                daemon_mod.restart_if_running(self.home, self.config)
                self._send_json(HTTPStatus.OK, {"id": wf.id, "enabled": new_state})
            except Exception as e:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(e)})
            return

        # Update schedule via JSON API
        if path.startswith("/api/schedules/") and path.endswith("/update"):
            wf_id = path[len("/api/schedules/"):-len("/update")]
            new_schedule = (json_payload.get("schedule") or form_data.get("schedule", [""])[0]).strip()
            try:
                wf = workflow_mod.load(self.home, wf_id)
                text = wf.path.read_text()
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    import re
                    front, body = parts[1], parts[2]
                    if re.search(r"^\s*schedule\s*:", front, flags=re.MULTILINE):
                        front = re.sub(r"(^\s*schedule\s*:).*$", rf'\g<1> "{new_schedule}"', front, flags=re.MULTILINE)
                    elif re.search(r"^\s*trigger\s*:", front, flags=re.MULTILINE):
                        front = re.sub(r"(^\s*trigger\s*:.*$)", rf'\g<1>\n  schedule: "{new_schedule}"', front, flags=re.MULTILINE)
                    else:
                        front = front + f'\ntrigger:\n  schedule: "{new_schedule}"\n'
                    updated_text = "---" + front + "---" + body
                else:
                    updated_text = text

                authoring.write_file(
                    self.home,
                    wf.path,
                    updated_text,
                    evidence=f"schedule updated to '{new_schedule}' for {wf.id} via api"
                )
                daemon_mod.restart_if_running(self.home, self.config)
                self._send_json(HTTPStatus.OK, {"id": wf.id, "schedule": new_schedule})
            except Exception as e:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(e)})
            return

        # Trigger workflow run via JSON API
        if path.startswith("/api/workflows/") and path.endswith("/trigger"):
            wf_id = path[len("/api/workflows/"):-len("/trigger")]
            try:
                cli_inputs = {}
                inputs_src = json_payload.get("inputs") or {}
                if isinstance(inputs_src, dict):
                    cli_inputs.update(inputs_src)
                for k, v in form_data.items():
                    if k.startswith("var_") and v:
                        cli_inputs[k[len("var_"):]] = v[0]
                    elif k in ("input", "inputs") and v:
                        cli_inputs[k] = v[0]

                def _bg_run():
                    try:
                        runner.run(
                            self.home,
                            self.config,
                            wf_id,
                            trigger="manual",
                            cli_inputs=cli_inputs,
                        )
                    except Exception:
                        pass

                t = threading.Thread(target=_bg_run, daemon=True)
                t.start()
                self._send_json(HTTPStatus.ACCEPTED, {"status": "triggered", "workflow_id": wf_id})
            except Exception as e:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(e)})
            return

        # Approve queued write via JSON API
        if path.startswith("/api/approvals/") and path.endswith("/approve"):
            approval_id = path[len("/api/approvals/"):-len("/approve")]
            try:
                result = approvals_mod.approve(self.home, self.config, approval_id)
                self._send_json(HTTPStatus.OK, result)
            except approvals_mod.ApprovalError as e:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(e)})
            return

        # Reject queued write via JSON API
        if path.startswith("/api/approvals/") and path.endswith("/reject"):
            approval_id = path[len("/api/approvals/"):-len("/reject")]
            reason = json_payload.get("reason") or form_data.get("reason", [""])[0]
            try:
                result = approvals_mod.reject(self.home, self.config, approval_id, reason=reason)
                self._send_json(HTTPStatus.OK, result)
            except approvals_mod.ApprovalError as e:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(e)})
            return

        # Mark inbox entry via JSON API
        if path.startswith("/api/inbox/") and path.endswith("/mark"):
            entry_id = path[len("/api/inbox/"):-len("/mark")]
            new_status = json_payload.get("status") or form_data.get("status", [inbox_mod.READ])[0]
            try:
                updated_entry = inbox_mod.mark(self.home, entry_id, new_status)
                self._send_json(HTTPStatus.OK, updated_entry)
            except inbox_mod.InboxError as e:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(e)})
            return

        # Daemon action via JSON API
        if path == "/api/daemon/action":
            act = json_payload.get("act") or query.get("act", [""])[0]
            if act == "tick":
                try:
                    state = daemon_mod.load_schedule_state(self.home)
                    fired = daemon_mod.tick(self.home, self.config, state)
                    self._send_json(HTTPStatus.OK, {"status": "ok", "action": "tick", "fired": fired})
                except Exception as e:
                    self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(e)})
                return
            elif act == "start":
                try:
                    status = daemon_mod.status(self.home, self.config)
                    if not status.get("alive"):
                        try:
                            daemon_mod.spawn_serve(self.home)
                        except OSError as oe:
                            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(oe)})
                            return
                        import time; time.sleep(0.5)
                        status = daemon_mod.status(self.home, self.config)
                    self._send_json(HTTPStatus.OK, status)
                except Exception as e:
                    self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(e)})
                return
            elif act == "stop":
                try:
                    status = daemon_mod.status(self.home, self.config)
                    if status.get("alive") and status.get("pid"):
                        os.kill(status["pid"], signal.SIGTERM)
                    import time; time.sleep(0.5)
                    new_status = daemon_mod.status(self.home, self.config)
                    self._send_json(HTTPStatus.OK, new_status)
                except Exception as e:
                    self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(e)})
                return

        self._send_response(HTTPStatus.NOT_FOUND, b"Endpoint not found", "text/plain")

    def _send_response(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: HTTPStatus, data: Any) -> None:
        body = json.dumps(data, default=str).encode("utf-8")
        self._send_response(status, body, "application/json")

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy standard request logging to keep console clean
        pass


def start_server(home: Path, config: dict, host: str = "127.0.0.1", port: int = 8080, open_browser: bool = True) -> None:
    handler = WebUIHandler
    handler.home = home
    handler.config = config

    server_address = (host, port)
    # Allow port reuse
    socketserver.TCPServer.allow_reuse_address = True
    try:
        httpd = ThreadingHTTPServer(server_address, handler)
    except OSError as e:
        # If default port is in use, try next ports
        if port == 8080:
            for next_port in range(8081, 8090):
                try:
                    server_address = (host, next_port)
                    httpd = ThreadingHTTPServer(server_address, handler)
                    port = next_port
                    break
                except OSError:
                    continue
            else:
                raise e
        else:
            raise e

    url = f"http://{host}:{port}/"
    ui.ok("web dashboard running", url)
    ui.hint("Ctrl-C to stop the server")

    if open_browser:
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping web dashboard...")
    finally:
        httpd.server_close()
