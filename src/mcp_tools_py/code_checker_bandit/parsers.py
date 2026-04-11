"""
Functions for parsing bandit JSON output.
"""

import json
import logging
import os

from .models import BanditMessage

logger = logging.getLogger(__name__)


def parse_bandit_json_output(
    raw_output: str,
    project_dir: str,
) -> tuple[list[BanditMessage], list[str], str | None]:
    """Parse bandit --format json output into BanditMessage objects.

    Args:
        raw_output: Raw JSON output from bandit
        project_dir: Project root directory for path normalization

    Returns:
        Tuple of (messages, file_errors, parse_error_string_or_none)
    """
    messages: list[BanditMessage] = []
    file_errors: list[str] = []

    if not raw_output or raw_output.strip() == "":
        logger.info("Bandit produced no output")
        return messages, file_errors, None

    try:
        data = json.loads(raw_output)
        if not isinstance(data, dict):
            error_message = (
                f"Expected JSON object from bandit, got {type(data).__name__}"
            )
            logger.error(
                "Invalid bandit output format",
                extra={"output_type": type(data).__name__},
            )
            return messages, file_errors, error_message

        logger.debug(
            "Successfully parsed bandit JSON output",
            extra={"results_count": len(data.get("results", []))},
        )

        for error_item in data.get("errors", []):
            if isinstance(error_item, dict):
                filename = error_item.get("filename", "unknown")
                reason = error_item.get("reason", "unknown error")
                file_errors.append(f"{filename}: {reason}")

        for item in data.get("results", []):
            if not isinstance(item, dict):
                logger.warning(
                    "Skipping non-dict item in bandit results",
                    extra={"item_type": type(item).__name__},
                )
                continue

            filename = item.get("filename", "")
            if filename:
                filename = os.path.relpath(filename, project_dir)

            issue_cwe = item.get("issue_cwe") or {}
            cwe_id = issue_cwe.get("id", 0) if isinstance(issue_cwe, dict) else 0
            cwe_link = issue_cwe.get("link", "") if isinstance(issue_cwe, dict) else ""

            messages.append(
                BanditMessage(
                    test_id=item.get("test_id", ""),
                    test_name=item.get("test_name", ""),
                    issue_severity=item.get("issue_severity", ""),
                    issue_confidence=item.get("issue_confidence", ""),
                    issue_text=item.get("issue_text", ""),
                    filename=filename,
                    line_number=item.get("line_number", 0),
                    more_info=item.get("more_info", ""),
                    cwe_id=cwe_id,
                    cwe_link=cwe_link,
                )
            )
    except json.JSONDecodeError as e:
        if len(raw_output) > 200:
            error_message = (
                f"Failed to parse bandit JSON output: {e}. "
                f"First 200 chars of output: {raw_output[:200]}..."
            )
        else:
            error_message = (
                f"Failed to parse bandit JSON output: {e}. Output: {raw_output}"
            )

        logger.error(
            "JSON parse error",
            extra={
                "error": str(e),
                "output_length": len(raw_output),
                "output_preview": raw_output[:100],
            },
        )
        return messages, file_errors, error_message

    return messages, file_errors, None
