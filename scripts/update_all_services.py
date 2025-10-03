#!/usr/bin/env python3
"""Update all services with *, org_id: int parameter (Stage 19.3)."""

import re
from pathlib import Path

SERVICES_TO_UPDATE = {
    "pricing_service.py": ["compute_pricing_for_skus"],
    "reviews_service.py": ["build_reply_for_review"],
    "reviews_sla.py": [
        "update_first_reply_timestamp",
        "compute_review_sla",
        "find_overdue_reviews",
    ],
    "supply_planner.py": ["generate_supply_plan", "build_advice_explanation"],
    "cashflow_pnl.py": [
        "recompute_pnl",
        "recompute_cashflow",
        "run_scenario",
        "run_reconciliation",
    ],
}


def update_function_signature(content: str, func_name: str) -> str:
    """Add *, org_id: int to function signature after db parameter."""

    # Pattern: def func_name(\n    db: Session,
    pattern = rf"(def {func_name}\(\s*\n\s+db:\s*Session,)"

    # Check if org_id already exists
    if re.search(rf"def {func_name}\([^)]*org_id", content):
        return content  # Already has org_id

    # Replace with: def func_name(\n    db: Session,\n    *,\n    org_id: int,
    replacement = r"\1\n    *,\n    org_id: int,"

    return re.sub(pattern, replacement, content)


def add_org_id_to_select(content: str) -> str:
    """Add .where(Model.org_id == org_id) to select() statements."""

    # This is complex and error-prone with regex, so we'll add a comment
    # indicating manual review needed

    return content


def process_service_file(filepath: Path, functions: list[str]) -> bool:
    """Update a service file."""
    content = filepath.read_text()
    original = content

    # Update each function
    for func in functions:
        content = update_function_signature(content, func)

    # Add exec_scoped import if not present
    if "exec_scoped" in content and "from app.db.utils import" not in content:
        # Add import
        imports_section = content.split("\n\n")[0]
        if "from sqlalchemy" in imports_section:
            content = content.replace(
                "from sqlalchemy", "from app.db.utils import exec_scoped\nfrom sqlalchemy", 1
            )

    if content != original:
        filepath.write_text(content)
        print(f"✓ Updated {filepath.name}: {', '.join(functions)}")
        return True
    else:
        print(f"- No changes: {filepath.name}")
        return False


def main():
    """Update all services."""
    services_dir = Path("app/services")

    updated = []
    for service_file, functions in SERVICES_TO_UPDATE.items():
        filepath = services_dir / service_file
        if not filepath.exists():
            print(f"✗ {service_file} not found")
            continue

        if process_service_file(filepath, functions):
            updated.append(service_file)

    print(f"\n✓ Updated {len(updated)}/{len(SERVICES_TO_UPDATE)} service files")
    print("\n⚠ CRITICAL: Manual review required:")
    print("  1. Add WHERE org_id = :org_id to ALL SQL queries in services")
    print("  2. Add .where(Model.org_id == org_id) to ALL ORM queries")
    print("  3. Wrap text() SQL in exec_scoped(db, sql, params, org_id)")
    print("  4. Update router calls to pass org_id=org_id")


if __name__ == "__main__":
    main()
