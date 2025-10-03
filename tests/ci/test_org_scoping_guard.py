"""Tests for CI org scoping guard script (Stage 19 Hardening)."""

from __future__ import annotations

from pathlib import Path


def test_ci_guard_script_exists() -> None:
    """Test CI guard script exists and is executable."""
    script_path = Path("scripts/ci/check_org_scope.sh")

    assert script_path.exists(), "CI guard script not found"
    assert script_path.is_file(), "CI guard script is not a file"
    # Check if executable bit is set
    assert script_path.stat().st_mode & 0o111, "CI guard script is not executable"


def test_ci_guard_script_has_shebang() -> None:
    """Test CI guard script has proper shebang."""
    script_path = Path("scripts/ci/check_org_scope.sh")

    with open(script_path) as f:
        first_line = f.readline().strip()

    assert first_line == "#!/bin/bash", "CI guard script missing proper shebang"


def test_ci_guard_detects_business_tables() -> None:
    """Test CI guard script contains all business tables."""
    script_path = Path("scripts/ci/check_org_scope.sh")

    with open(script_path) as f:
        content = f.read()

    # Check for key business tables
    expected_tables = [
        "reviews",
        "sku",
        "daily_sales",
        "pricing_advice",
        "cashflow",
    ]

    for table in expected_tables:
        assert f'"{table}"' in content, f"CI guard missing table: {table}"


def test_ci_guard_checks_select_queries() -> None:
    """Test CI guard script checks SELECT queries."""
    script_path = Path("scripts/ci/check_org_scope.sh")

    with open(script_path) as f:
        content = f.read()

    assert "SELECT" in content, "CI guard doesn't check SELECT queries"
    assert "org_id" in content, "CI guard doesn't check for org_id"


def test_ci_guard_checks_insert_queries() -> None:
    """Test CI guard script checks INSERT queries."""
    script_path = Path("scripts/ci/check_org_scope.sh")

    with open(script_path) as f:
        content = f.read()

    assert "INSERT" in content, "CI guard doesn't check INSERT queries"


def test_ci_guard_checks_pokupatel_usage() -> None:
    """Test CI guard script checks for forbidden 'покупатель' word."""
    script_path = Path("scripts/ci/check_org_scope.sh")

    with open(script_path) as f:
        content = f.read()

    assert "покупатель" in content, "CI guard doesn't check for 'покупатель'"
    assert "replies.py" in content, "CI guard doesn't check reply templates"


def test_ci_guard_excludes_migrations() -> None:
    """Test CI guard script excludes migrations from checks."""
    script_path = Path("scripts/ci/check_org_scope.sh")

    with open(script_path) as f:
        content = f.read()

    assert "migrations/" in content, "CI guard doesn't exclude migrations"
    assert "grep -v" in content or "exclude" in content.lower()


def test_ci_guard_excludes_tests() -> None:
    """Test CI guard script excludes test files from checks."""
    script_path = Path("scripts/ci/check_org_scope.sh")

    with open(script_path) as f:
        content = f.read()

    assert "test_" in content, "CI guard doesn't exclude test files"


def test_ci_guard_has_proper_exit_codes() -> None:
    """Test CI guard script has proper exit code handling."""
    script_path = Path("scripts/ci/check_org_scope.sh")

    with open(script_path) as f:
        content = f.read()

    assert "exit 0" in content, "CI guard missing success exit code"
    assert "exit 1" in content, "CI guard missing failure exit code"
    assert "FOUND_ISSUES" in content or "violations" in content.lower()


def test_ci_guard_provides_help_on_failure() -> None:
    """Test CI guard script provides helpful error messages."""
    script_path = Path("scripts/ci/check_org_scope.sh")

    with open(script_path) as f:
        content = f.read()

    # Should provide guidance on fixing issues
    assert "exec_scoped" in content, "CI guard doesn't mention exec_scoped"
    assert "OrgScope" in content, "CI guard doesn't mention OrgScope"


def test_ci_guard_checks_router_dependencies() -> None:
    """Test CI guard script checks routers import OrgScope."""
    script_path = Path("scripts/ci/check_org_scope.sh")

    with open(script_path) as f:
        content = f.read()

    assert "app/web/routers" in content, "CI guard doesn't check routers"
    assert "import" in content.lower(), "CI guard doesn't check imports"
