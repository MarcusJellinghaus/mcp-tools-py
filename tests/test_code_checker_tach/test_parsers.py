"""Tests for code_checker_tach.parsers, against output probed from tach 0.35.3."""

from mcp_tools_py.code_checker_tach.parsers import TachDiagnostic, parse_tach_json

# `tach check --output json`, exit code 1: two undeclared imports and one use
# of a dependency declared `deprecated = true`.
VIOLATIONS_JSON = r"""[
  {
    "Located": {
      "file_path": "a\\x.py",
      "line_number": 1,
      "original_line_number": 1,
      "severity": "Error",
      "details": {
        "Code": {
          "UndeclaredDependency": {
            "dependency": "b",
            "usage_module": "a",
            "definition_module": "b"
          }
        }
      }
    }
  },
  {
    "Located": {
      "file_path": "a\\x.py",
      "line_number": 2,
      "original_line_number": 2,
      "severity": "Error",
      "details": {
        "Code": {
          "UndeclaredDependency": {
            "dependency": "b.y",
            "usage_module": "a",
            "definition_module": "b"
          }
        }
      }
    }
  },
  {
    "Located": {
      "file_path": "c\\z.py",
      "line_number": 1,
      "original_line_number": 1,
      "severity": "Warning",
      "details": {
        "Code": {
          "DeprecatedDependency": {
            "dependency": "b.y",
            "usage_module": "c",
            "definition_module": "b"
          }
        }
      }
    }
  }
]
"""

# Exit code 0: a project with no first-party imports.
GLOBAL_WARNING_JSON = """[
  {
    "Global": {
      "severity": "Warning",
      "details": {
        "Configuration": {
          "NoFirstPartyImportsFound": []
        }
      }
    }
  }
]
"""

# Exit code 1: a broken tach.toml prints plain text on stdout.
CONFIG_ERROR_TEXT = """\
Failed to parse project config: TOML parse error at line 1, column 11
  |
1 | [[modules]
  |           ^
unclosed array table, expected `]`
"""


def test_located_diagnostics_are_parsed() -> None:
    assert parse_tach_json(VIOLATIONS_JSON) == [
        TachDiagnostic(
            "a/x.py", 1, "error", "UndeclaredDependency", "a", "b",
            "UndeclaredDependency: a -> b",
        ),
        TachDiagnostic(
            "a/x.py", 2, "error", "UndeclaredDependency", "a", "b",
            "UndeclaredDependency: a -> b",
        ),
        TachDiagnostic(
            "c/z.py", 1, "warning", "DeprecatedDependency", "c", "b",
            "DeprecatedDependency: c -> b",
        ),
    ]  # fmt: skip


def test_global_diagnostic_has_no_location() -> None:
    assert parse_tach_json(GLOBAL_WARNING_JSON) == [
        TachDiagnostic(
            None, None, "warning", "NoFirstPartyImportsFound", None, None,
            "NoFirstPartyImportsFound",
        )
    ]  # fmt: skip


def test_empty_list_is_no_diagnostics() -> None:
    assert parse_tach_json("[]") == []


def test_error_dict_is_unknown_shape() -> None:
    assert parse_tach_json('{"error": "config not found"}') is None


def test_plain_text_is_unknown_shape() -> None:
    assert parse_tach_json(CONFIG_ERROR_TEXT) is None


def test_unknown_item_shape_is_unknown() -> None:
    assert parse_tach_json('[{"Located": {"severity": "Error"}}]') is None
