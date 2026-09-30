"""Functions for parsing pylint output."""

import json
import logging
from typing import List

from .models import PylintMessage

logger = logging.getLogger(__name__)


def _invalid_reason(item: object) -> str | None:
    """Why a pylint JSON entry cannot be used as a message, or None if valid."""
    if not isinstance(item, dict):
        return "entries that are not objects"
    if any(item.get(key) is None for key in ("path", "symbol", "message-id")):
        return "entries without path, symbol or message-id"
    if not all(
        isinstance(item.get(key), int) and not isinstance(item.get(key), bool)
        for key in ("line", "column")
    ):
        return "entries without locations"
    return None


def parse_pylint_json_output(
    raw_output: str,
) -> tuple[List[PylintMessage], str | None]:
    """Parse pylint JSON output into PylintMessage objects.

    Args:
        raw_output: Raw JSON output from pylint

    Returns:
        Tuple of (list of PylintMessage objects, error message if any)
    """
    messages: List[PylintMessage] = []
    error_message = None

    # Check if we have any output to parse
    if not raw_output or raw_output.strip() == "":
        logger.info("Pylint produced no output")
        return messages, None

    try:
        pylint_output = json.loads(raw_output)
        if not isinstance(pylint_output, list):
            error_message = (
                f"Expected JSON array from pylint, got {type(pylint_output).__name__}"
            )
            logger.error(
                "Invalid pylint output format",
                extra={"output_type": type(pylint_output).__name__},
            )
            return messages, error_message

        for item in pylint_output:
            reason = _invalid_reason(item)
            if reason:
                keys = (
                    ", ".join(item) if isinstance(item, dict) else type(item).__name__
                )
                error_message = (
                    f"pylint returned {reason} (keys: {keys}); an argument in "
                    "extra_args probably changed the output shape."
                )
                logger.error("Invalid pylint output entry", extra={"reason": reason})
                return [], error_message

        # Log details about JSON parsing success
        logger.debug(
            "Successfully parsed pylint JSON output",
            extra={
                "json_array_length": len(pylint_output),
                "first_item_keys": (
                    list(pylint_output[0].keys()) if pylint_output else None
                ),
            },
        )

        for item in pylint_output:
            messages.append(
                PylintMessage(
                    type=item.get("type", ""),
                    module=item.get("module", ""),
                    obj=item.get("obj", ""),
                    line=item["line"],
                    column=item["column"],
                    path=item["path"],
                    symbol=item["symbol"],
                    message=item.get("message", ""),
                    message_id=item["message-id"],
                )
            )
    except json.JSONDecodeError as e:
        if len(raw_output) > 200:
            error_message = (
                f"Failed to parse Pylint JSON output: {e}. "
                f"First 200 chars of output: {raw_output[:200]}..."
            )
        else:
            error_message = (
                f"Failed to parse Pylint JSON output: {e}. Output: {raw_output}"
            )

        logger.error(
            "JSON parse error",
            extra={
                "error": str(e),
                "output_length": len(raw_output),
                "output_preview": raw_output[:100],
            },
        )

    return messages, error_message
