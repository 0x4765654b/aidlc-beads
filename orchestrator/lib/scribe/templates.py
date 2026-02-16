"""Template application for artifact generation."""

from __future__ import annotations

from pathlib import Path

from orchestrator.lib.scribe.workspace import find_workspace_root, TEMPLATES_DIR


def apply_template(template_name: str, variables: dict[str, str]) -> str:
    """Load a template from templates/ and fill in variables.

    Variables in the template use {variable_name} syntax.

    Args:
        template_name: Filename of the template (e.g., "artifact-header.md").
        variables: Dictionary of variable names to values.

    Returns:
        The filled template as a string.

    Raises:
        FileNotFoundError: If the template file doesn't exist.
        KeyError: If a required variable is missing from the variables dict.
    """
    root = find_workspace_root()
    template_path = root / TEMPLATES_DIR / template_name

    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    template_content = template_path.read_text(encoding="utf-8")

    # Use str.format_map with a custom dict that raises KeyError for missing keys
    try:
        return template_content.format_map(variables)
    except KeyError as e:
        raise KeyError(
            f"Missing template variable {e} in template '{template_name}'. "
            f"Available variables: {list(variables.keys())}"
        ) from e
