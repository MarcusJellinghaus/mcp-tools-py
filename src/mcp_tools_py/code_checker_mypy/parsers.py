"""Parser for mypy JSON output."""

import json
import logging

from mcp_tools_py.code_checker_mypy.models import MypyMessage

logger = logging.getLogger(__name__)


def parse_mypy_json_output(output: str) -> tuple[list[MypyMessage], str | None]:
    """Parse mypy JSON output into MypyMessage objects.

    Mypy outputs one JSON object per line when using --output json.

    Args:
        output: Raw output from mypy command

    Returns:
        Tuple of (messages list, error string if parsing failed)
    """
    messages = []
    parse_errors = []

    for line_num, line in enumerate(output.splitlines(), 1):
        line = line.strip()
        if not line:
            continue

        try:
            data = json.loads(line)

            # Extract fields with defaults
            message = MypyMessage(
                file=data.get("file", ""),
                line=data.get("line", 0),
                column=data.get("column", 0),
                severity=data.get("severity", "error"),
                message=data.get("message", ""),
                code=data.get("code"),
                hint=data.get("hint"),
            )
            messages.append(message)

        except json.JSONDecodeError:
            # Some lines might not be JSON (like summary text)
            logger.debug(
                "Non-JSON line in mypy output",
                extra={"line_num": line_num, "content": line[:100]},
            )
        except (AttributeError, KeyError, TypeError, ValueError) as e:
            parse_errors.append(f"Line {line_num}: {str(e)}")

    if parse_errors and not messages:
        error_msg = f"Failed to parse mypy output: {'; '.join(parse_errors)}"
        return [], error_msg

    logger.debug(
        "Parsed mypy output",
        extra={
            "total_messages": len(messages),
            "severities": list({msg.severity for msg in messages}),
        },
    )

    return messages, None


def strip_json_messages(output: str) -> str:
    """Remove the lines `parse_mypy_json_output` reads as messages.

    A message is a line that parses as a JSON object. Other JSON values, such
    as `null` or `123`, are kept.

    Args:
        output: Text mixing mypy JSON messages with anything else

    Returns:
        The remaining lines joined with newlines and stripped
    """
    kept_lines = []
    for line in output.splitlines():
        try:
            is_message = isinstance(json.loads(line), dict)
        except json.JSONDecodeError:
            is_message = False
        if not is_message:
            kept_lines.append(line)

    return "\n".join(kept_lines).strip()
