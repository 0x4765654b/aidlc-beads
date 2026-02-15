#!/usr/bin/env python3
"""
sync-outline.py -- Bidirectional sync between aidlc-docs/ and Outline Wiki.

This script synchronizes markdown artifacts between the local git repository
and a self-hosted Outline instance, enabling non-technical users to review
and edit AIDLC documents through Outline's WYSIWYG web interface.

Usage:
    # Push local markdown files to Outline
    python scripts/sync-outline.py push

    # Pull edits from Outline back to local files
    python scripts/sync-outline.py pull

    # Full bidirectional sync (push then pull)
    python scripts/sync-outline.py sync

    # Show sync status (what's changed on each side)
    python scripts/sync-outline.py status

    # Initialize Outline collection structure from aidlc-docs/
    python scripts/sync-outline.py init

Environment:
    Configure via outline/.env or environment variables:
    - OUTLINE_API_KEY: API key from Outline settings
    - OUTLINE_API_URL: Base URL (default: http://localhost:3000/api)
    - OUTLINE_COLLECTION_NAME: Collection name (default: AIDLC Documents)
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

try:
    import requests
    from dotenv import load_dotenv
    from rich.console import Console
    from rich.table import Table
except ImportError:
    print("Missing dependencies. Install with: pip install -r scripts/requirements.txt")
    sys.exit(1)

# ─── Configuration ──────────────────────────────────────────────────────────

# Load .env from outline/ directory
ENV_PATH = Path(__file__).parent.parent / "outline" / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)

OUTLINE_API_URL = os.getenv("OUTLINE_API_URL", "http://localhost:3000/api")
OUTLINE_API_KEY = os.getenv("OUTLINE_API_KEY", "")
OUTLINE_COLLECTION_NAME = os.getenv("OUTLINE_COLLECTION_NAME", "AIDLC Documents")

PROJECT_ROOT = Path(__file__).parent.parent
AIDLC_DOCS_DIR = PROJECT_ROOT / "aidlc-docs"
SYNC_STATE_FILE = PROJECT_ROOT / ".beads" / "outline-sync-state.json"

console = Console()

# ─── Outline API Client ────────────────────────────────────────────────────


class OutlineClient:
    """Minimal Outline API client for document sync operations."""

    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })

    def _post(self, endpoint: str, data: dict | None = None) -> dict:
        """Make a POST request to the Outline API (RPC-style)."""
        url = f"{self.api_url}/{endpoint}"
        resp = self.session.post(url, json=data or {})
        resp.raise_for_status()
        return resp.json()

    # ── Collections ─────────────────────────────────────────────────────

    def list_collections(self) -> list[dict]:
        """List all collections."""
        result = self._post("collections.list", {"limit": 100})
        return result.get("data", [])

    def create_collection(self, name: str, description: str = "") -> dict:
        """Create a new collection."""
        result = self._post("collections.create", {
            "name": name,
            "description": description,
            "permission": "read_write",
        })
        return result.get("data", {})

    def find_collection(self, name: str) -> Optional[dict]:
        """Find a collection by name."""
        for col in self.list_collections():
            if col["name"] == name:
                return col
        return None

    # ── Documents ───────────────────────────────────────────────────────

    def list_documents(self, collection_id: str) -> list[dict]:
        """List all documents in a collection."""
        result = self._post("documents.list", {
            "collectionId": collection_id,
            "limit": 100,
        })
        return result.get("data", [])

    def get_document(self, doc_id: str) -> dict:
        """Get a single document by ID."""
        result = self._post("documents.info", {"id": doc_id})
        return result.get("data", {})

    def search_document_by_title(self, title: str, collection_id: str) -> Optional[dict]:
        """Search for a document by exact title within a collection."""
        result = self._post("documents.search", {
            "query": title,
            "collectionId": collection_id,
            "limit": 25,
        })
        for item in result.get("data", []):
            doc = item.get("document", item)
            if doc.get("title", "").strip() == title.strip():
                return doc
        return None

    def create_document(
        self,
        title: str,
        text: str,
        collection_id: str,
        parent_document_id: Optional[str] = None,
    ) -> dict:
        """Create a new document."""
        payload = {
            "title": title,
            "text": text,
            "collectionId": collection_id,
            "publish": True,
        }
        if parent_document_id:
            payload["parentDocumentId"] = parent_document_id
        result = self._post("documents.create", payload)
        return result.get("data", {})

    def update_document(self, doc_id: str, title: str, text: str) -> dict:
        """Update an existing document."""
        result = self._post("documents.update", {
            "id": doc_id,
            "title": title,
            "text": text,
        })
        return result.get("data", {})

    def delete_document(self, doc_id: str) -> None:
        """Delete a document."""
        self._post("documents.delete", {"id": doc_id})


# ─── Markdown Processing ───────────────────────────────────────────────────

# Pattern to match beads HTML comment headers
BEADS_HEADER_PATTERN = re.compile(
    r"^(<!--\s*beads-(?:issue|review):\s*\S+\s*-->\s*\n)+",
    re.MULTILINE,
)


def extract_title_and_body(markdown: str) -> tuple[str, str]:
    """Extract the H1 title and remaining body from a markdown document.

    Returns (title, body). The body includes beads headers as metadata
    comment at the end so they survive round-tripping through Outline.
    """
    # Strip beads headers from the top
    beads_headers = ""
    match = BEADS_HEADER_PATTERN.match(markdown)
    if match:
        beads_headers = match.group(0).strip()
        markdown = markdown[match.end():]

    # Extract the first H1 title
    title = "Untitled"
    lines = markdown.split("\n")
    body_lines = []
    title_found = False
    for line in lines:
        if not title_found and line.startswith("# "):
            title = line[2:].strip()
            title_found = True
        else:
            body_lines.append(line)

    body = "\n".join(body_lines).strip()

    # Append beads headers as a hidden metadata block at the end
    if beads_headers:
        body += f"\n\n---\n\n{beads_headers}"

    return title, body


def reconstruct_markdown(title: str, body: str) -> str:
    """Reconstruct a full markdown file from Outline title + body.

    Extracts beads headers from the metadata block at the end and
    places them back at the top of the file.
    """
    beads_headers = ""
    clean_body = body

    # Check for beads headers at the end (after last ---)
    parts = body.rsplit("\n\n---\n\n", 1)
    if len(parts) == 2:
        potential_headers = parts[1].strip()
        if potential_headers.startswith("<!-- beads-"):
            beads_headers = potential_headers
            clean_body = parts[0].strip()

    # Reconstruct
    lines = []
    if beads_headers:
        lines.append(beads_headers)
    lines.append(f"# {title}")
    if clean_body:
        lines.append("")
        lines.append(clean_body)
    lines.append("")  # Trailing newline

    return "\n".join(lines)


def compute_content_hash(content: str) -> str:
    """Compute a hash of the content for change detection."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


# ─── Sync State Management ─────────────────────────────────────────────────


def load_sync_state() -> dict:
    """Load the sync state from disk."""
    if SYNC_STATE_FILE.exists():
        with open(SYNC_STATE_FILE) as f:
            return json.load(f)
    return {"documents": {}, "collection_id": None, "last_sync": None}


def save_sync_state(state: dict) -> None:
    """Save the sync state to disk."""
    SYNC_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SYNC_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ─── Sync Operations ───────────────────────────────────────────────────────


def get_local_documents() -> dict[str, dict]:
    """Scan aidlc-docs/ and return a map of relative paths to metadata."""
    docs = {}
    if not AIDLC_DOCS_DIR.exists():
        return docs

    for md_file in sorted(AIDLC_DOCS_DIR.rglob("*.md")):
        rel_path = md_file.relative_to(PROJECT_ROOT).as_posix()
        content = md_file.read_text(encoding="utf-8")
        title, body = extract_title_and_body(content)
        docs[rel_path] = {
            "path": rel_path,
            "title": title,
            "body": body,
            "content_hash": compute_content_hash(content),
            "raw_content": content,
        }
    return docs


def ensure_collection(client: OutlineClient) -> str:
    """Ensure the AIDLC collection exists in Outline. Returns collection ID."""
    col = client.find_collection(OUTLINE_COLLECTION_NAME)
    if col:
        return col["id"]

    console.print(f"[yellow]Creating collection:[/yellow] {OUTLINE_COLLECTION_NAME}")
    col = client.create_collection(
        OUTLINE_COLLECTION_NAME,
        description="AIDLC workflow artifacts. Synced from git repository.",
    )
    return col["id"]


def cmd_init(client: OutlineClient) -> None:
    """Initialize the Outline collection and push all existing documents."""
    collection_id = ensure_collection(client)
    state = load_sync_state()
    state["collection_id"] = collection_id

    local_docs = get_local_documents()
    if not local_docs:
        console.print("[yellow]No documents found in aidlc-docs/. Nothing to initialize.[/yellow]")
        save_sync_state(state)
        return

    console.print(f"[green]Pushing {len(local_docs)} documents to Outline...[/green]")

    for rel_path, doc_info in local_docs.items():
        console.print(f"  Creating: {rel_path}")
        outline_doc = client.create_document(
            title=doc_info["title"],
            text=doc_info["body"],
            collection_id=collection_id,
        )
        state["documents"][rel_path] = {
            "outline_id": outline_doc["id"],
            "last_push_hash": doc_info["content_hash"],
            "last_pull_hash": doc_info["content_hash"],
        }

    state["last_sync"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save_sync_state(state)
    console.print(f"[green]Initialized {len(local_docs)} documents in Outline.[/green]")


def cmd_push(client: OutlineClient) -> None:
    """Push local changes to Outline."""
    state = load_sync_state()
    collection_id = state.get("collection_id")
    if not collection_id:
        console.print("[red]Not initialized. Run: python scripts/sync-outline.py init[/red]")
        return

    local_docs = get_local_documents()
    pushed = 0

    for rel_path, doc_info in local_docs.items():
        doc_state = state["documents"].get(rel_path)

        if doc_state is None:
            # New document -- create in Outline
            console.print(f"  [green]+ New:[/green] {rel_path}")
            outline_doc = client.create_document(
                title=doc_info["title"],
                text=doc_info["body"],
                collection_id=collection_id,
            )
            state["documents"][rel_path] = {
                "outline_id": outline_doc["id"],
                "last_push_hash": doc_info["content_hash"],
                "last_pull_hash": doc_info["content_hash"],
            }
            pushed += 1
        elif doc_info["content_hash"] != doc_state["last_push_hash"]:
            # Changed locally -- update in Outline
            console.print(f"  [yellow]~ Updated:[/yellow] {rel_path}")
            client.update_document(
                doc_id=doc_state["outline_id"],
                title=doc_info["title"],
                text=doc_info["body"],
            )
            state["documents"][rel_path]["last_push_hash"] = doc_info["content_hash"]
            pushed += 1

    state["last_sync"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save_sync_state(state)

    if pushed:
        console.print(f"[green]Pushed {pushed} document(s) to Outline.[/green]")
    else:
        console.print("[dim]No local changes to push.[/dim]")


def cmd_pull(client: OutlineClient) -> None:
    """Pull edits from Outline back to local files."""
    state = load_sync_state()
    collection_id = state.get("collection_id")
    if not collection_id:
        console.print("[red]Not initialized. Run: python scripts/sync-outline.py init[/red]")
        return

    pulled = 0

    for rel_path, doc_state in list(state["documents"].items()):
        outline_id = doc_state.get("outline_id")
        if not outline_id:
            continue

        try:
            outline_doc = client.get_document(outline_id)
        except requests.HTTPError:
            console.print(f"  [red]! Missing in Outline:[/red] {rel_path}")
            continue

        # Reconstruct the full markdown from Outline's title + body
        reconstructed = reconstruct_markdown(
            outline_doc["title"],
            outline_doc["text"],
        )
        outline_hash = compute_content_hash(reconstructed)

        if outline_hash != doc_state.get("last_pull_hash"):
            # Changed in Outline -- write to local file
            local_path = PROJECT_ROOT / rel_path
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(reconstructed, encoding="utf-8")

            console.print(f"  [cyan]<< Pulled:[/cyan] {rel_path}")
            state["documents"][rel_path]["last_pull_hash"] = outline_hash
            state["documents"][rel_path]["last_push_hash"] = outline_hash
            pulled += 1

    state["last_sync"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save_sync_state(state)

    if pulled:
        console.print(f"[green]Pulled {pulled} document(s) from Outline.[/green]")
    else:
        console.print("[dim]No remote changes to pull.[/dim]")


def cmd_sync(client: OutlineClient) -> None:
    """Full bidirectional sync: push local changes, then pull remote edits."""
    console.print("[bold]Push phase:[/bold]")
    cmd_push(client)
    console.print()
    console.print("[bold]Pull phase:[/bold]")
    cmd_pull(client)


def cmd_status(client: OutlineClient) -> None:
    """Show sync status: what's changed locally and remotely."""
    state = load_sync_state()
    collection_id = state.get("collection_id")

    if not collection_id:
        console.print("[red]Not initialized. Run: python scripts/sync-outline.py init[/red]")
        return

    local_docs = get_local_documents()
    table = Table(title="Outline Sync Status")
    table.add_column("File", style="cyan")
    table.add_column("Local", justify="center")
    table.add_column("Outline", justify="center")
    table.add_column("Status")

    for rel_path, doc_info in sorted(local_docs.items()):
        doc_state = state["documents"].get(rel_path)
        if doc_state is None:
            table.add_row(rel_path, "new", "-", "[green]New (not pushed)[/green]")
        elif doc_info["content_hash"] != doc_state["last_push_hash"]:
            table.add_row(rel_path, "changed", "?", "[yellow]Modified locally[/yellow]")
        else:
            table.add_row(rel_path, "ok", "ok", "[dim]In sync[/dim]")

    # Check for docs in state but not on disk (deleted locally)
    for rel_path in state["documents"]:
        if rel_path not in local_docs:
            table.add_row(rel_path, "deleted", "exists", "[red]Deleted locally[/red]")

    console.print(table)

    if state.get("last_sync"):
        console.print(f"\n[dim]Last sync: {state['last_sync']}[/dim]")


# ─── CLI Entry Point ───────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Sync AIDLC markdown artifacts with Outline Wiki.",
        epilog="See docs/design/outline-integration.md for setup instructions.",
    )
    parser.add_argument(
        "command",
        choices=["init", "push", "pull", "sync", "status"],
        help="Sync command to run.",
    )
    parser.add_argument(
        "--api-url",
        default=OUTLINE_API_URL,
        help=f"Outline API URL (default: {OUTLINE_API_URL})",
    )
    parser.add_argument(
        "--api-key",
        default=OUTLINE_API_KEY,
        help="Outline API key (or set OUTLINE_API_KEY env var)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without making changes.",
    )
    args = parser.parse_args()

    if not args.api_key:
        console.print(
            "[red]Error:[/red] OUTLINE_API_KEY not set. "
            "Create an API key at http://localhost:3000/settings/api "
            "and set it in outline/.env or pass --api-key."
        )
        sys.exit(1)

    client = OutlineClient(args.api_url, args.api_key)

    commands = {
        "init": cmd_init,
        "push": cmd_push,
        "pull": cmd_pull,
        "sync": cmd_sync,
        "status": cmd_status,
    }
    commands[args.command](client)


if __name__ == "__main__":
    main()
