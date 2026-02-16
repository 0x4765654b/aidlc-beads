<!-- beads-issue: gt-17 -->
<!-- beads-review: gt-18 -->
# Functional Design -- Unit 1: Scribe Tool Library

## Overview

Scribe is a **Python tool library** (not an agent) that provides deterministic artifact management functions. Every Chimp agent uses Scribe to create, validate, register, and sync AIDLC artifacts. Scribe has no LLM dependency -- all operations are pure Python.

**Module path**: `orchestrator/lib/scribe/`

---

## Data Models

### ArtifactHeader

```python
@dataclass
class ArtifactHeader:
    """Parsed cross-reference header from a markdown artifact."""
    beads_issue: str          # e.g., "gt-17"
    beads_review: str | None  # e.g., "gt-18" (None if no review gate)
```

### ValidationResult

```python
@dataclass
class ValidationResult:
    """Result of artifact validation."""
    valid: bool
    errors: list[str]         # e.g., ["Missing beads-issue header", "Wrong directory"]
    warnings: list[str]       # e.g., ["beads-review header missing (optional)"]
    path: Path
```

### ArtifactInfo

```python
@dataclass
class ArtifactInfo:
    """Metadata about an artifact file."""
    path: Path
    header: ArtifactHeader
    title: str                # First H1 heading
    stage: str                # Inferred from directory (e.g., "reverse-engineering")
    phase: str                # "inception" or "construction"
    size_bytes: int
    last_modified: datetime
```

---

## Module: `headers.py` -- Cross-Reference Header Management

### `parse_header(content: str) -> ArtifactHeader`

Parse the beads-issue and beads-review HTML comments from markdown content.

**Rules**:
- Headers MUST be the first lines of the file (before any markdown content)
- `<!-- beads-issue: ... -->` is required
- `<!-- beads-review: ... -->` is optional
- Whitespace and blank lines between headers are tolerated
- If beads-issue is missing, raise `ValueError`

**Input**: Raw markdown string
**Output**: `ArtifactHeader` dataclass
**Errors**: `ValueError` if beads-issue header is missing or malformed

### `write_header(beads_issue: str, beads_review: str | None = None) -> str`

Generate the header string to prepend to artifact content.

**Output**: String like:
```
<!-- beads-issue: gt-17 -->
<!-- beads-review: gt-18 -->
```

### `strip_header(content: str) -> str`

Remove the beads-issue and beads-review comment lines from content, returning only the body.

---

## Module: `artifacts.py` -- Core Artifact Functions

### `create_artifact(stage: str, name: str, content: str, beads_issue_id: str, review_gate_id: str | None = None, phase: str = "inception") -> Path`

Create a markdown artifact file with correct headers, directory placement, and naming.

**Business Rules**:
1. Directory: `aidlc-docs/{phase}/{stage}/{name}.md`
   - Inception stages: `aidlc-docs/inception/{stage}/`
   - Construction stages: `aidlc-docs/construction/{unit-name}/`
2. Prepend cross-reference headers using `write_header()`
3. Create parent directories if they don't exist
4. If file already exists, raise `FileExistsError` (no silent overwrite)
5. Return the absolute path to the created file

**Input**:
- `stage`: Directory name (e.g., "reverse-engineering", "unit-1-scribe")
- `name`: File name without extension (e.g., "architecture", "functional-design")
- `content`: Markdown body (without headers -- headers are prepended)
- `beads_issue_id`: Issue ID for the beads-issue header
- `review_gate_id`: Optional review gate ID for the beads-review header
- `phase`: "inception" or "construction" (default "inception")

**Output**: `Path` to the created file
**Errors**: `FileExistsError`, `ValueError` (invalid stage/name)

### `update_artifact(path: Path, content: str) -> Path`

Update an existing artifact's body content while preserving its headers.

**Business Rules**:
1. Read existing file, parse headers
2. Replace body content (everything after headers) with new content
3. Write back with original headers preserved
4. If file doesn't exist, raise `FileNotFoundError`

### `validate_artifact(path: Path) -> ValidationResult`

Validate an artifact file for correctness.

**Validation checks**:
1. File exists and is readable
2. Has valid `beads-issue` header
3. Has at least one H1 heading (`# ...`)
4. Path matches expected directory structure (`aidlc-docs/{phase}/{stage}/`)
5. File is not empty (beyond headers)
6. Optional: `beads-review` header present (warning if missing, not error)

**Output**: `ValidationResult` with valid flag, errors list, warnings list

### `register_artifact(beads_issue_id: str, artifact_path: Path) -> None`

Update the Beads issue notes field with `artifact: <path>`.

**Business Rules**:
1. Run: `bd update {beads_issue_id} --append-notes "artifact: {artifact_path}"`
2. If the bd command fails, raise `subprocess.CalledProcessError`
3. Path is stored relative to workspace root (e.g., `aidlc-docs/inception/requirements/requirements.md`)

### `list_stage_artifacts(stage_name: str, phase: str = "inception") -> list[ArtifactInfo]`

List all artifacts in a stage directory with metadata.

**Business Rules**:
1. Scan `aidlc-docs/{phase}/{stage_name}/` for `.md` files
2. Parse headers and title from each file
3. Return sorted by filename
4. If directory doesn't exist, return empty list (not error)

---

## Module: `outline_sync.py` -- Outline Push/Pull Wrapper

### `sync_to_outline() -> None`

Push local artifacts to Outline Wiki.

**Implementation**: Run `python scripts/sync-outline.py push` as subprocess.

**Error handling**: Capture stderr. If the script fails (non-zero exit), log the error and raise `RuntimeError` with the stderr content. Do NOT fail silently -- Outline sync failures must be visible.

### `pull_from_outline() -> None`

Pull edits from Outline back to local files.

**Implementation**: Run `python scripts/sync-outline.py pull` as subprocess.

**Error handling**: Same as `sync_to_outline()`.

### `outline_sync_status() -> dict`

Get the current sync state.

**Implementation**: Run `python scripts/sync-outline.py status` and parse the output.

---

## Module: `templates.py` -- Template Application

### `apply_template(template_name: str, variables: dict) -> str`

Load a template from `templates/` and fill in variables.

**Business Rules**:
1. Load `templates/{template_name}` (e.g., `artifact-header.md`)
2. Replace `{variable_name}` placeholders with values from the dict
3. If a required variable is missing, raise `KeyError`
4. If the template file doesn't exist, raise `FileNotFoundError`
5. Return the filled template as a string

---

## Configuration

### Workspace Root Detection

All path operations are relative to the **workspace root** -- the directory containing the `.beads/` folder.

```python
def find_workspace_root(start: Path = None) -> Path:
    """Walk up from start (default: cwd) until .beads/ is found."""
```

If `.beads/` is not found within 10 parent directories, raise `RuntimeError("Not in a Beads workspace")`.

### Constants

```python
AIDLC_DOCS_DIR = "aidlc-docs"
TEMPLATES_DIR = "templates"
SYNC_SCRIPT = "scripts/sync-outline.py"
```

---

## Error Handling Strategy

| Error | Behavior |
|-------|----------|
| File already exists on create | Raise `FileExistsError` |
| File not found on update/validate | Raise `FileNotFoundError` |
| Missing beads-issue header | Raise `ValueError` |
| bd CLI fails | Raise `subprocess.CalledProcessError` |
| sync-outline.py fails | Raise `RuntimeError` with stderr |
| Template variable missing | Raise `KeyError` |
| Not in Beads workspace | Raise `RuntimeError` |

All functions use standard Python exceptions. No custom exception classes in V1 -- keep it simple.

---

## Dependencies

- **Python stdlib**: `pathlib`, `subprocess`, `dataclasses`, `re`, `datetime`
- **External**: None (Scribe has zero pip dependencies)
- **System**: `bd` CLI must be on PATH, `python` must be able to run `scripts/sync-outline.py`
