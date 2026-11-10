"""Parser for `tach check --output json`."""

import json
from typing import Any, NamedTuple


class TachDiagnostic(NamedTuple):
    """One tach diagnostic.

    `file`/`line` are None for global diagnostics (e.g. configuration
    warnings). `dependency` is the definition module, else the import path.
    """

    file: str | None
    line: int | None
    severity: str
    kind: str
    usage_module: str | None
    dependency: str | None
    message: str


def _kind_and_fields(details: Any) -> tuple[str, dict[str, Any]] | None:
    """Unwrap `{"<Category>": {"<Kind>": {fields}}}` or `{"<Category>": "<Kind>"}`.

    Returns:
        The kind and its fields, or None when `details` has another shape.
    """
    if not isinstance(details, dict) or len(details) != 1:
        return None
    (inner,) = details.values()
    if isinstance(inner, str):
        return inner, {}
    if not isinstance(inner, dict) or len(inner) != 1:
        return None
    ((kind, fields),) = inner.items()
    return kind, fields if isinstance(fields, dict) else {}


def _optional_str(fields: dict[str, Any], *names: str) -> str | None:
    for name in names:
        value = fields.get(name)
        if isinstance(value, str) and value:
            return value
    return None


def _diagnostic(item: Any) -> TachDiagnostic | None:
    if not isinstance(item, dict) or len(item) != 1:
        return None
    (body,) = item.values()
    if not isinstance(body, dict) or not isinstance(body.get("severity"), str):
        return None
    unwrapped = _kind_and_fields(body.get("details"))
    if unwrapped is None:
        return None
    kind, fields = unwrapped

    file_path = body.get("file_path")
    line = body.get("line_number")
    usage_module = _optional_str(fields, "usage_module")
    dependency = _optional_str(
        fields, "definition_module", "import_mod_path", "dependency"
    )
    message = (
        f"{kind}: {usage_module} -> {dependency}"
        if usage_module and dependency
        else _optional_str(fields, "message") or kind
    )
    return TachDiagnostic(
        file=file_path.replace("\\", "/") if isinstance(file_path, str) else None,
        line=line if isinstance(line, int) else None,
        severity=body["severity"].lower(),
        kind=kind,
        usage_module=usage_module,
        dependency=dependency,
        message=message,
    )


def parse_tach_json(stdout: str) -> list[TachDiagnostic] | None:
    """Parse tach's JSON diagnostics list.

    Returns:
        The diagnostics, or None when `stdout` is not a list of known
        diagnostics (plain text, `{"error": ...}`, an unknown shape).
    """
    try:
        data = json.loads(stdout)
    except ValueError:
        return None
    if not isinstance(data, list):
        return None
    diagnostics = [_diagnostic(item) for item in data]
    if any(diagnostic is None for diagnostic in diagnostics):
        return None
    return [diagnostic for diagnostic in diagnostics if diagnostic is not None]
