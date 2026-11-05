"""Saved coverage data of the target project.

Everything lives in ``.mcp-tools-py/coverage/`` below the project: the metadata
in ``last_run.json``, replaced last so a failed save leaves the previous one
readable, and one ``run-<uuid>.coverage`` data file per run it references.
"""

import contextlib
import hashlib
import json
import logging
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp_tools_py.code_checker_pytest.coverage import (
    COVERAGE_DATA,
    RunOutcome,
    norm_path,
    run_outcome,
)
from mcp_tools_py.code_checker_pytest.models import PytestReport
from mcp_tools_py.code_checker_pytest.verdict import RunVerdict
from mcp_tools_py.utils.file_utils import read_file
from mcp_tools_py.utils.project_config import (
    get_test_directories,
    resolve_coverage_source,
)

logger = logging.getLogger(__name__)

STORE_DIR = os.path.join(".mcp-tools-py", "coverage")
METADATA_FILE = "last_run.json"
STORE_VERSION = 1

_UNREADABLE = "unreadable"
_SELECTION_PREFIX = "selection: "
_METADATA_KEYS = ("report", "hashes", "roots", "sources", "fail_under", "runs")
_RUN_KEYS = (
    "selection",
    "data_file",
    "failed_collectors",
    "failed_tests",
    "generic_warning",
)


@dataclass
class CoverageRun:
    """What is known about a coverage run before pytest starts."""

    project_dir: str
    temp_dir: str
    sources: list[str]
    roots: list[str]
    hashes: dict[str, str]
    fail_under: float | None
    selection: str


@dataclass
class FinishedRun:
    """What the digest of a finished coverage run is rendered from."""

    data: dict[str, Any] | None
    selection: str
    outcome: RunOutcome
    notes: list[str]


def start_coverage_run(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    project_dir: str,
    temp_dir: str,
    test_folder: str,
    coverage_source: list[str] | None,
    sources: list[str],
    fail_under: float | None,
    selection: str,
) -> CoverageRun:
    """Record the state of the project right before a coverage run.

    Args:
        project_dir: Path to the target project.
        temp_dir: Directory the run writes its report and data file into.
        test_folder: The test folder of the run.
        coverage_source: The caller's raw ``coverage_source``, for the roots.
        sources: The resolved directories to measure.
        fail_under: The project's ``fail_under``, if it could be read.
        selection: The selection line of the run.

    Returns:
        The run, with its freshness roots and their hashes at this moment.
    """
    roots = freshness_roots(project_dir, coverage_source, test_folder)
    return CoverageRun(
        project_dir=project_dir,
        temp_dir=temp_dir,
        sources=sorted(norm_path(source) for source in sources),
        roots=roots,
        hashes=hash_python_files(project_dir, roots),
        fail_under=fail_under,
        selection=selection,
    )


def finish_coverage_run(
    run: CoverageRun,
    data: dict[str, Any] | None,
    report: PytestReport | None,
    verdict: RunVerdict,
) -> FinishedRun:
    """Save the data of a finished run, or clear saved data when it has none.

    A failed update is logged and becomes a note; it never fails the run.

    Args:
        run: The value returned by :func:`start_coverage_run`.
        data: The coverage JSON, or None when the run left no usable report.
        report: The parsed pytest report, if any.
        verdict: The verdict of the run.

    Returns:
        The report, selection and outcome to render, and any notes to show.
    """
    outcome = run_outcome(report, verdict)
    notes = []
    try:
        if data is None:
            clear_saved(run.project_dir)
        else:
            write_saved(
                run.project_dir,
                {
                    "report": data,
                    "hashes": run.hashes,
                    "roots": run.roots,
                    "sources": run.sources,
                    "fail_under": run.fail_under,
                    "runs": [
                        {"selection": run.selection, "data_file": None, **outcome}
                    ],
                },
                os.path.join(run.temp_dir, COVERAGE_DATA),
            )
    except OSError as exc:
        note = f"Could not update saved coverage data: {exc}"
        logger.warning(note)
        notes.append(note)
    return FinishedRun(data, run.selection, outcome, notes)


def view_of_runs(runs: list[dict[str, Any]]) -> tuple[str, RunOutcome]:
    """Reduce saved run entries to what a digest shows for them together.

    Args:
        runs: The ``runs`` entries of the metadata.

    Returns:
        One selection line, with identical selections listed once, and the
        summed outcome.
    """
    selections = dict.fromkeys(
        run["selection"].removeprefix(_SELECTION_PREFIX) for run in runs
    )
    return _SELECTION_PREFIX + " + ".join(selections), RunOutcome(
        failed_collectors=sum(run["failed_collectors"] for run in runs),
        failed_tests=sum(run["failed_tests"] for run in runs),
        generic_warning=any(run["generic_warning"] for run in runs),
    )


def freshness_roots(
    project_dir: str, coverage_source: list[str] | None, test_folder: str
) -> list[str]:
    """List the directories whose Python files decide if saved data is fresh.

    Args:
        project_dir: Path to the target project.
        coverage_source: The caller's raw ``coverage_source``; entries that are
            package names are not directories and drop out.
        test_folder: The test folder of the run.

    Returns:
        The configured source and test directories, *coverage_source* and
        *test_folder*: normalized, deduped, and only those on disk.
    """
    resolved = resolve_coverage_source(project_dir, None)
    candidates = [] if isinstance(resolved, str) else list(resolved)
    candidates += coverage_source or []
    try:
        candidates += get_test_directories(project_dir)
    except ValueError:
        pass
    candidates.append(test_folder)

    unique = dict.fromkeys(norm_path(candidate) for candidate in candidates)
    return [root for root in unique if os.path.isdir(os.path.join(project_dir, root))]


def hash_python_files(project_dir: str, roots: list[str]) -> dict[str, str]:
    """Hash the Python files below the roots.

    Hidden directories, ``__pycache__`` and virtual environments are not walked.

    Args:
        project_dir: Path to the target project.
        roots: Directories to walk, relative to *project_dir* or absolute.

    Returns:
        SHA-256 digests by POSIX path relative to *project_dir*, or by the
        file's own path when it has none, as on another Windows drive. A file
        that can't be read has the digest ``unreadable``.
    """
    hashes: dict[str, str] = {}
    for root in roots:
        for directory, subdirs, names in os.walk(os.path.join(project_dir, root)):
            subdirs[:] = [
                name
                for name in subdirs
                if not name.startswith(".")
                and name != "__pycache__"
                and not os.path.exists(os.path.join(directory, name, "pyvenv.cfg"))
            ]
            for name in names:
                if name.endswith(".py"):
                    path = os.path.join(directory, name)
                    hashes[_hash_key(project_dir, path)] = _digest(path)
    return hashes


def _hash_key(project_dir: str, path: str) -> str:
    """Build the key of one file in the hash mapping.

    Returns:
        The POSIX path relative to *project_dir*, or *path* in POSIX form when
        there is no relative path.
    """
    try:
        return Path(os.path.relpath(path, project_dir)).as_posix()
    except ValueError:
        return Path(path).as_posix()


def _digest(path: str) -> str:
    """Hash one file.

    Returns:
        The SHA-256 hex digest, or ``unreadable`` on an OSError.
    """
    try:
        with open(path, "rb") as file:
            return hashlib.file_digest(file, "sha256").hexdigest()
    except OSError:
        return _UNREADABLE


def _store_dir(project_dir: str) -> str:
    """Locate the store directory of a project.

    Returns:
        The path of the store directory, which may not exist.
    """
    return os.path.join(project_dir, STORE_DIR)


def _is_valid_metadata(saved: object) -> bool:
    """Check the structure the code reading saved data relies on.

    Returns:
        True when *saved* is metadata of this version with the right shape.
    """
    if not isinstance(saved, dict) or saved.get("version") != STORE_VERSION:
        return False
    if any(key not in saved for key in _METADATA_KEYS):
        return False
    report = saved["report"]
    runs = saved["runs"]
    return (
        isinstance(report, dict)
        and isinstance(report.get("files"), dict)
        and isinstance(saved["hashes"], dict)
        and isinstance(saved["roots"], list)
        and isinstance(saved["sources"], list)
        and isinstance(runs, list)
        and all(
            isinstance(run, dict) and all(key in run for key in _RUN_KEYS)
            for run in runs
        )
    )


def load_saved(project_dir: str) -> dict[str, Any] | None:
    """Read the saved metadata.

    This is the only guard against corrupt metadata: code reading the result
    relies on the structure checked here.

    Args:
        project_dir: Path to the target project.

    Returns:
        The metadata; None when it is absent, unparsable, of another version or
        of the wrong shape.
    """
    try:
        saved = json.loads(
            read_file(os.path.join(_store_dir(project_dir), METADATA_FILE))
        )
    except (OSError, ValueError):
        return None
    return saved if _is_valid_metadata(saved) else None


def write_saved(
    project_dir: str, saved: dict[str, Any], new_data_file: str | None
) -> None:
    """Save a run set, replacing the previous metadata.

    An ``OSError`` propagates; the previous metadata stays until the replace.

    Args:
        project_dir: Path to the target project.
        saved: The metadata. Updated in place: this sets ``version`` and the
            newest run's ``data_file``.
        new_data_file: The newest run's coverage data file, copied into the
            store. A missing file leaves ``data_file`` None.
    """
    store = _store_dir(project_dir)
    os.makedirs(store, exist_ok=True)
    gitignore = os.path.join(store, ".gitignore")
    if not os.path.exists(gitignore):
        with open(gitignore, "w", encoding="utf-8") as file:
            file.write("*")

    data_file = None
    if new_data_file is not None and os.path.isfile(new_data_file):
        data_file = f"run-{uuid.uuid4()}.coverage"
        shutil.copyfile(new_data_file, os.path.join(store, data_file))
    saved["runs"][-1]["data_file"] = data_file
    saved["version"] = STORE_VERSION

    _replace_metadata(store, json.dumps(saved, separators=(",", ":")))

    referenced = {run["data_file"] for run in saved["runs"]}
    for path in Path(store).glob("run-*.coverage"):
        if path.name not in referenced:
            path.unlink()


def _replace_metadata(store: str, content: str) -> None:
    """Atomically replace the metadata file, leaving no temp file on failure.

    Args:
        store: The store directory.
        content: The new content of the metadata file.

    Raises:
        OSError: If the temp file can't be written or moved into place.
    """
    descriptor, temp_path = tempfile.mkstemp(dir=store, suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(content)
        os.replace(temp_path, os.path.join(store, METADATA_FILE))
    except OSError:
        with contextlib.suppress(OSError):
            os.unlink(temp_path)
        raise


def clear_saved(project_dir: str) -> None:
    """Remove the saved data; an ``OSError`` propagates.

    Args:
        project_dir: Path to the target project. Nothing is created when it has
            no store.
    """
    store = _store_dir(project_dir)
    if os.path.isdir(store):
        shutil.rmtree(store)
