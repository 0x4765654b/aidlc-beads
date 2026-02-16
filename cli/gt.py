"""gt -- Gorilla Troop CLI.

Thin command-line wrapper over the Orchestrator API.
Sends HTTP requests and prints formatted output.

Usage:
    gt [--api-url URL] COMMAND [OPTIONS]
"""

from __future__ import annotations

import json
import sys
from typing import Any

import click
import httpx

DEFAULT_API_URL = "http://localhost:9741"


class ApiClient:
    """Simple HTTP client for the Orchestrator API."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        params: dict | None = None,
    ) -> Any:
        """Make an HTTP request and return parsed JSON.

        Raises:
            click.ClickException: On connection or HTTP errors.
        """
        url = f"{self.base_url}{path}"
        try:
            resp = httpx.request(
                method, url, json=json_body, params=params, timeout=30.0
            )
        except httpx.ConnectError:
            raise click.ClickException(
                f"Cannot connect to Orchestrator API at {self.base_url}"
            )
        except httpx.TimeoutException:
            raise click.ClickException("Request timed out")

        if resp.status_code == 204:
            return None
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise click.ClickException(f"API error ({resp.status_code}): {detail}")

        return resp.json()

    def get(self, path: str, **params: Any) -> Any:
        clean = {k: v for k, v in params.items() if v is not None}
        return self._request("GET", path, params=clean)

    def post(self, path: str, body: dict | None = None) -> Any:
        return self._request("POST", path, json_body=body)

    def delete(self, path: str) -> Any:
        return self._request("DELETE", path)


# Store the client in Click context
pass_client = click.make_pass_decorator(ApiClient, ensure=True)


@click.group()
@click.option(
    "--api-url",
    default=DEFAULT_API_URL,
    envvar="GT_API_URL",
    help="Orchestrator API base URL.",
    show_default=True,
)
@click.pass_context
def cli(ctx: click.Context, api_url: str) -> None:
    """gt -- Gorilla Troop command-line interface."""
    ctx.ensure_object(dict)
    ctx.obj = ApiClient(api_url)


# ── status ────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("project_key", required=False)
@click.pass_obj
def status(client: ApiClient, project_key: str | None) -> None:
    """Show project status. Without PROJECT_KEY, lists all projects."""
    if project_key:
        data = client.get(f"/api/projects/{project_key}/status")
        click.echo(f"Project: {data['project_key']} ({data['name']})")
        click.echo(f"Status: {data['status']}")
        click.echo(f"Phase: {data.get('current_phase', 'unknown')}")
        click.echo(f"Active Agents: {data.get('active_agents', 0)}")
        click.echo(f"Pending Reviews: {data.get('pending_reviews', 0)}")
        click.echo(f"Open Questions: {data.get('open_questions', 0)}")
    else:
        projects = client.get("/api/projects/")
        if not projects:
            click.echo("No projects found.")
            return
        click.echo("Projects:")
        for p in projects:
            indicator = "●" if p["status"] == "active" else "○"
            click.echo(
                f"  {indicator} {p['project_key']:<20s} {p['status']:<12s} {p['name']}"
            )


# ── projects ──────────────────────────────────────────────────────────────


@cli.group()
def projects() -> None:
    """Manage projects."""


@projects.command("list")
@click.option("--status", "filter_status", default=None, help="Filter by status.")
@click.pass_obj
def projects_list(client: ApiClient, filter_status: str | None) -> None:
    """List all projects."""
    params = {"status": filter_status} if filter_status else {}
    data = client.get("/api/projects/", **params)
    if not data:
        click.echo("No projects found.")
        return
    click.echo(f"{'KEY':<20s} {'NAME':<25s} {'STATUS':<12s} {'CREATED'}")
    for p in data:
        created = p.get("created_at", "")[:10]
        click.echo(
            f"{p['project_key']:<20s} {p['name']:<25s} {p['status']:<12s} {created}"
        )


@projects.command("create")
@click.argument("key")
@click.argument("name")
@click.argument("workspace_path")
@click.pass_obj
def projects_create(
    client: ApiClient, key: str, name: str, workspace_path: str
) -> None:
    """Create a new project."""
    data = client.post(
        "/api/projects/",
        {"key": key, "name": name, "workspace_path": workspace_path},
    )
    click.echo(f"✓ Created project: {data['project_key']} ({data['name']})")


@projects.command("pause")
@click.argument("key")
@click.pass_obj
def projects_pause(client: ApiClient, key: str) -> None:
    """Pause a project."""
    client.post(f"/api/projects/{key}/pause")
    click.echo(f"✓ Paused project: {key}")


@projects.command("resume")
@click.argument("key")
@click.pass_obj
def projects_resume(client: ApiClient, key: str) -> None:
    """Resume a project."""
    client.post(f"/api/projects/{key}/resume")
    click.echo(f"✓ Resumed project: {key}")


@projects.command("delete")
@click.argument("key")
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt.")
@click.pass_obj
def projects_delete(client: ApiClient, key: str, confirm: bool) -> None:
    """Delete a project."""
    if not confirm:
        click.confirm(f"Delete project '{key}'? This cannot be undone", abort=True)
    client.delete(f"/api/projects/{key}")
    click.echo(f"✓ Deleted project: {key}")


# ── approve / reject ─────────────────────────────────────────────────────


@cli.command()
@click.argument("issue_id")
@click.option("--feedback", default="", help="Optional feedback text.")
@click.pass_obj
def approve(client: ApiClient, issue_id: str, feedback: str) -> None:
    """Approve a review gate."""
    data = client.post(
        f"/api/review/{issue_id}/approve", {"feedback": feedback}
    )
    click.echo(f"✓ Review {issue_id} approved. {data.get('message', '')}")


@cli.command()
@click.argument("issue_id")
@click.option("--feedback", required=True, help="Feedback text (required).")
@click.pass_obj
def reject(client: ApiClient, issue_id: str, feedback: str) -> None:
    """Reject a review gate (request changes)."""
    data = client.post(
        f"/api/review/{issue_id}/reject", {"feedback": feedback}
    )
    click.echo(f"✕ Review {issue_id} rejected. {data.get('message', '')}")
    click.echo(f'  Feedback: "{feedback}"')


# ── reviews ───────────────────────────────────────────────────────────────


@cli.command()
@click.option("--project", default=None, help="Filter by project.")
@click.pass_obj
def reviews(client: ApiClient, project: str | None) -> None:
    """List pending review gates."""
    data = client.get("/api/review/", project_key=project)
    if not data:
        click.echo("No pending reviews.")
        return
    click.echo("Pending Reviews:")
    for r in data:
        click.echo(f"  {r['issue_id']:<8s} {r['title']:<35s} {r.get('project_key', '')}")


# ── questions ─────────────────────────────────────────────────────────────


@cli.group(invoke_without_command=True)
@click.option("--project", default=None, help="Filter by project.")
@click.pass_context
def questions(ctx: click.Context, project: str | None) -> None:
    """List or answer pending questions."""
    if ctx.invoked_subcommand is None:
        client: ApiClient = ctx.obj
        data = client.get("/api/questions/", project_key=project)
        if not data:
            click.echo("No pending questions.")
            return
        click.echo("Pending Questions:")
        for q in data:
            click.echo(
                f"  {q['issue_id']:<8s} {q['title']:<35s} {q.get('project_key', '')}"
            )


@questions.command("answer")
@click.argument("issue_id")
@click.argument("answer_text")
@click.pass_obj
def questions_answer(client: ApiClient, issue_id: str, answer_text: str) -> None:
    """Answer a pending question."""
    data = client.post(
        f"/api/questions/{issue_id}/answer", {"answer": answer_text}
    )
    click.echo(f"✓ Question {issue_id} answered. {data.get('message', '')}")


# ── notifications ─────────────────────────────────────────────────────────


@cli.group(invoke_without_command=True)
@click.option("--project", default=None, help="Filter by project.")
@click.option("--limit", default=20, help="Max notifications.", show_default=True)
@click.pass_context
def notifications(ctx: click.Context, project: str | None, limit: int) -> None:
    """View notifications."""
    if ctx.invoked_subcommand is None:
        client: ApiClient = ctx.obj
        data = client.get(
            "/api/notifications/", project_key=project, limit=limit
        )
        if not data:
            click.echo("No unread notifications.")
            return
        for n in data:
            dot = "●" if not n["read"] else "○"
            click.echo(
                f"  {dot} [P{n['priority']}] {n['title']}"
            )
            click.echo(
                f"    {n['project_key']}  {n.get('created_at', '')[:19]}"
            )


@notifications.command("read")
@click.argument("notification_id")
@click.pass_obj
def notifications_read(client: ApiClient, notification_id: str) -> None:
    """Mark a notification as read."""
    client.post(f"/api/notifications/{notification_id}/read")
    click.echo(f"✓ Marked {notification_id} as read.")


@notifications.command("read-all")
@click.option("--project", default=None, help="Filter by project.")
@click.pass_obj
def notifications_read_all(client: ApiClient, project: str | None) -> None:
    """Mark all notifications as read."""
    params = {"project_key": project} if project else {}
    data = client.post(f"/api/notifications/read-all?{'&'.join(f'{k}={v}' for k, v in params.items())}")
    count = data.get("marked", 0) if data else 0
    click.echo(f"✓ Marked {count} notifications as read.")


# ── chat ──────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("message")
@click.option("--project", default=None, help="Project context.")
@click.pass_obj
def chat(client: ApiClient, message: str, project: str | None) -> None:
    """Send a message to Harmbe."""
    data = client.post(
        "/api/chat/", {"message": message, "project_key": project}
    )
    click.echo(f"Harmbe: {data.get('response', '')}")


# ── info ──────────────────────────────────────────────────────────────────


@cli.command()
@click.pass_obj
def info(client: ApiClient) -> None:
    """Show system information."""
    data = client.get("/api/info")
    click.echo(f"Gorilla Troop v{data.get('version', '?')}")
    click.echo(f"Active Projects: {data.get('active_projects', 0)}")
    click.echo(f"Active Agents: {data.get('active_agents', 0)}")
    click.echo(f"Pending Notifications: {data.get('pending_notifications', 0)}")
    click.echo(f"Engine: {data.get('engine_status', 'unknown')}")


# ── entry point ───────────────────────────────────────────────────────────


def main() -> None:
    """Entry point for the gt command."""
    cli()


if __name__ == "__main__":
    main()
