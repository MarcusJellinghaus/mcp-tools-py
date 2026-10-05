"""Functions for parsing bandit JSON output."""

import json
import logging
import os

from .models import BanditMessage

logger = logging.getLogger(__name__)


def _invalid_reason(item: object) -> str | None:
    """Why a bandit result entry cannot be used as a finding, or None if valid.

    Returns:
        A short reason the entry is unusable, or None if the entry is valid.
    """
    if not isinstance(item, dict):
        return "results that are not objects"
    if item.get("test_id") is None or item.get("filename") is None:
        return "results without test_id or filename"
    line_number = item.get("line_number")
    if not isinstance(line_number, int) or isinstance(line_number, bool):
        return "results without line numbers"
    return None


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

        results = data.get("results")
        if not isinstance(results, list):
            error_message = (
                f"bandit output has no 'results' list (keys: {', '.join(data)})"
            )
            logger.error("Invalid bandit output format", extra={"keys": list(data)})
            return messages, file_errors, error_message

        logger.debug(
            "Successfully parsed bandit JSON output",
            extra={"results_count": len(results)},
        )

        for error_item in data.get("errors", []):
            if isinstance(error_item, dict):
                filename = error_item.get("filename", "unknown")
                reason = error_item.get("reason", "unknown error")
                file_errors.append(f"{filename}: {reason}")

        for item in results:
            reason = _invalid_reason(item)
            if reason:
                keys = (
                    ", ".join(item) if isinstance(item, dict) else type(item).__name__
                )
                error_message = (
                    f"bandit returned {reason} (keys: {keys}); an argument in "
                    "extra_args probably changed the output shape."
                )
                logger.error("Invalid bandit result entry", extra={"reason": reason})
                return [], [], error_message

        for item in results:
            filename = item["filename"]
            if filename:
                # Bandit reports paths relative to its cwd, which is project_dir
                try:
                    filename = os.path.relpath(
                        os.path.join(project_dir, filename), project_dir
                    )
                except ValueError:
                    pass  # other drive: keep the path unchanged

            issue_cwe = item.get("issue_cwe")
            cwe_id = (issue_cwe.get("id") or 0) if isinstance(issue_cwe, dict) else 0
            cwe_link = (
                (issue_cwe.get("link") or "") if isinstance(issue_cwe, dict) else ""
            )

            messages.append(
                BanditMessage(
                    test_id=item["test_id"],
                    test_name=item.get("test_name", ""),
                    issue_severity=item.get("issue_severity", ""),
                    issue_confidence=item.get("issue_confidence", ""),
                    issue_text=item.get("issue_text", ""),
                    filename=filename,
                    line_number=item["line_number"],
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
