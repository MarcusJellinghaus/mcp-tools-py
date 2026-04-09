"""
Functions for parsing ruff output.
"""

import json
import logging
import os
from typing import List

from .models import RuffMessage

logger = logging.getLogger(__name__)


def parse_ruff_json_output(
    raw_output: str,
    project_dir: str,
) -> tuple[List[RuffMessage], str | None]:
    """
    Parse ruff --output-format=json output into RuffMessage objects.

    Args:
        raw_output: Raw JSON output from ruff
        project_dir: Project root directory for path normalization

    Returns:
        Tuple of (list of RuffMessage objects, error message if any)
    """
    messages: List[RuffMessage] = []

    if not raw_output or raw_output.strip() == "":
        logger.info("Ruff produced no output")
        return messages, None

    try:
        data = json.loads(raw_output)
        if not isinstance(data, list):
            error_message = f"Expected JSON array from ruff, got {type(data).__name__}"
            logger.error(
                "Invalid ruff output format",
                extra={"output_type": type(data).__name__},
            )
            return messages, error_message

        logger.debug(
            "Successfully parsed ruff JSON output",
            extra={"json_array_length": len(data)},
        )

        for item in data:
            if not isinstance(item, dict):
                logger.warning(
                    "Skipping non-dict item in ruff output",
                    extra={"item_type": type(item).__name__},
                )
                continue

            location = item.get("location", {})
            end_location = item.get("end_location", {})
            filename = item.get("filename", "")
            if filename:
                filename = os.path.relpath(filename, project_dir)

            messages.append(
                RuffMessage(
                    code=item.get("code", ""),
                    message=item.get("message", ""),
                    filename=filename,
                    line=location.get("row", -1),
                    column=location.get("column", -1),
                    end_line=end_location.get("row", -1),
                    end_column=end_location.get("column", -1),
                    url=item.get("url", ""),
                    fixable=bool(item.get("fix")),
                    noqa_row=item.get("noqa_row", -1),
                )
            )
    except json.JSONDecodeError as e:
        if len(raw_output) > 200:
            error_message = (
                f"Failed to parse ruff JSON output: {e}. "
                f"First 200 chars of output: {raw_output[:200]}..."
            )
        else:
            error_message = (
                f"Failed to parse ruff JSON output: {e}. Output: {raw_output}"
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

    return messages, None
