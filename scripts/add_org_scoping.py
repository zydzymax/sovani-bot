#!/usr/bin/env python3
"""Auto-add org_id scoping to routers (Stage 19.2)."""

import re
from pathlib import Path

ROUTERS_TO_UPDATE = [
    "inventory.py",
    "advice.py",
    "supply.py",
    "finance.py",
    "export.py",
    "bi_export.py",
    "reviews_sla.py",
]


def add_org_scope_import(content: str) -> str:
    """Add OrgScope to imports if not present."""
    # Check if already imported
    if "OrgScope" in content:
        return content

    # Find deps import line
    pattern = r"(from app\.web\.deps import [^\n]+)"
    match = re.search(pattern, content)

    if match:
        old_import = match.group(1)
        # Add OrgScope if not there
        if "OrgScope" not in old_import:
            new_import = old_import.rstrip(")").rstrip() + ", OrgScope"
            if not old_import.endswith("("):
                new_import = old_import + ", OrgScope"
            content = content.replace(old_import, new_import)

    return content


def add_org_id_param(content: str) -> str:
    """Add org_id: OrgScope parameter to all @router endpoints."""

    # Pattern to find @router.* functions
    pattern = r"(@router\.(get|post|put|patch|delete)\([^\)]*\)\s*\n(?:async )?def \w+\(\s*)"

    def replacer(match):
        decorator_and_def = match.group(0)
        # Add org_id param after opening paren
        if "org_id" not in decorator_and_def:
            # Insert after "def func_name("
            return decorator_and_def + "\n    org_id: OrgScope,"
        return decorator_and_def

    return re.sub(pattern, replacer, content)


def process_router(filepath: Path) -> bool:
    """Process a single router file."""
    print(f"Processing {filepath.name}...")

    content = filepath.read_text()
    original = content

    # Add imports
    content = add_org_scope_import(content)

    # Add exec_scoped import if text() SQL is used
    if "text(" in content and "exec_scoped" not in content:
        # Add exec_scoped import
        if "from app.db.utils import" in content:
            content = content.replace(
                "from app.db.utils import", "from app.db.utils import exec_scoped,"
            )
        elif "from app.web.deps import" in content:
            # Add new import line after deps
            deps_line_pattern = r"(from app\.web\.deps import [^\n]+\n)"
            content = re.sub(
                deps_line_pattern, r"\1from app.db.utils import exec_scoped\n", content
            )

    # Add org_id parameters (manual review needed after)
    # content = add_org_id_param(content)

    if content != original:
        filepath.write_text(content)
        print(f"  ✓ Updated {filepath.name}")
        return True
    else:
        print(f"  - No changes needed for {filepath.name}")
        return False


def main():
    """Process all routers."""
    routers_dir = Path("app/web/routers")

    updated = []
    for router_file in ROUTERS_TO_UPDATE:
        filepath = routers_dir / router_file
        if not filepath.exists():
            print(f"  ✗ {router_file} not found")
            continue

        if process_router(filepath):
            updated.append(router_file)

    print(f"\nUpdated {len(updated)}/{len(ROUTERS_TO_UPDATE)} routers")
    print("Note: Manual review and additional changes required:")
    print("  - Add org_id: OrgScope to all endpoint signatures")
    print("  - Add .where(Model.org_id == org_id) to ORM queries")
    print("  - Wrap text() SQL in exec_scoped()")


if __name__ == "__main__":
    main()
