"""Cross-reference header management for AIDLC artifacts."""

from __future__ import annotations

import re

from orchestrator.lib.scribe.models import ArtifactHeader

# Regex patterns for header comments
_ISSUE_PATTERN = re.compile(r"<!--\s*beads-issue:\s*(\S+)\s*-->")
_REVIEW_PATTERN = re.compile(r"<!--\s*beads-review:\s*(\S+)\s*-->")


def parse_header(content: str) -> ArtifactHeader:
    """Parse beads-issue and beads-review HTML comments from markdown content.

    Headers must appear in the first 10 lines of the file.

    Args:
        content: Raw markdown string.

    Returns:
        ArtifactHeader with parsed values.

    Raises:
        ValueError: If beads-issue header is missing or malformed.
    """
    # Only search the first 10 lines for headers
    header_lines = content.split("\n", 10)[:10]
    header_text = "\n".join(header_lines)

    issue_match = _ISSUE_PATTERN.search(header_text)
    if not issue_match:
        raise ValueError(
            "Missing required beads-issue header. "
            "Expected: <!-- beads-issue: <id> --> in the first lines of the file."
        )

    review_match = _REVIEW_PATTERN.search(header_text)

    return ArtifactHeader(
        beads_issue=issue_match.group(1),
        beads_review=review_match.group(1) if review_match else None,
    )


def write_header(beads_issue: str, beads_review: str | None = None) -> str:
    """Generate the header string to prepend to artifact content.

    Args:
        beads_issue: The Beads issue ID (e.g., "gt-17").
        beads_review: Optional review gate ID (e.g., "gt-18").

    Returns:
        Header string with trailing newline.
    """
    lines = [f"<!-- beads-issue: {beads_issue} -->"]
    if beads_review:
        lines.append(f"<!-- beads-review: {beads_review} -->")
    return "\n".join(lines) + "\n"


def strip_header(content: str) -> str:
    """Remove beads-issue and beads-review comment lines from content.

    Returns only the body content (everything after the header comments).

    Args:
        content: Raw markdown string with headers.

    Returns:
        Markdown body without header comments.
    """
    lines = content.split("\n")
    body_start = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "" or _ISSUE_PATTERN.match(stripped) or _REVIEW_PATTERN.match(stripped):
            body_start = i + 1
        else:
            break

    return "\n".join(lines[body_start:])
