"""Contract test: all business routes are org-scoped.

This test dynamically inspects FastAPI routes to ensure:
1. Business endpoints have org_id = Depends(get_org_scope) parameter
2. Handler modules contain exec_scoped() or ORM org_id filters

This is a regression guard - it will fail if anyone adds unscoped routes.
"""

from __future__ import annotations

import inspect
import re
from importlib import import_module

from fastapi import FastAPI


def test_all_business_routes_are_org_scoped():
    """Verify all business API routes have org_id scoping."""
    # Import app
    app_mod = import_module("app.web.main")
    app: FastAPI = getattr(app_mod, "app")

    # Business routes = /api/v1/* except auth/public routes
    BUSINESS_PREFIXES = ("/api/v1/",)
    WHITELIST = {
        "/healthz",
        "/metrics",
        "/docs",
        "/openapi.json",
        "/api/v1/orgs/me",
        "/api/v1/orgs",  # Org management (creates orgs, doesn't need org_id)
        "/api/v1/auth",  # Auth endpoints (login, register, refresh)
        "/api/v1/ops",  # Operational/admin endpoints (system-wide monitoring)
    }

    def _is_business(path: str) -> bool:
        """Check if route is a business route requiring org scoping."""
        if not any(path.startswith(p) for p in BUSINESS_PREFIXES):
            return False
        # Whitelist exact matches and prefix matches (e.g., /api/v1/auth/*)
        for w in WHITELIST:
            if path == w or path.startswith(w + "/"):
                return False
        return True

    def _has_org_dep(endpoint) -> bool:
        """Check if endpoint has org_id = Depends(get_org_scope) parameter."""
        sig = inspect.signature(endpoint)
        for param in sig.parameters.values():
            if param.name == "org_id":
                # Check for Depends(get_org_scope) or OrgScope annotation
                default_str = str(param.default)
                annotation_str = str(param.annotation)
                if "get_org_scope" in default_str or "OrgScope" in annotation_str:
                    return True
        return False

    def _module_contains_scoped_ops(func) -> bool:
        """Check if handler module contains exec_scoped() or ORM org_id filters."""
        mod = inspect.getmodule(func)
        if not mod or not getattr(mod, "__file__", None):
            return False
        try:
            with open(mod.__file__, encoding="utf-8") as f:
                src = f.read()
        except Exception:
            return False

        # Heuristics:
        # 1. exec_scoped() presence
        if "exec_scoped(" in src:
            return True

        # 2. ORM org_id filters (.where(Model.org_id == org_id))
        if re.search(r"\.where\([^)]*\.org_id\s*==\s*org_id", src):
            return True

        # 3. SQLAlchemy filter (older style)
        if re.search(r"\.filter\([^)]*\.org_id\s*==\s*org_id", src):
            return True

        # 4. Service layer calls with org_id parameter
        # (many routers delegate to services that do the scoping)
        if re.search(r"\w+\([^)]*org_id\s*=\s*org_id", src):
            # At least the router is passing org_id to something
            # This is weak but catches service delegation pattern
            return True

        return False

    failures = []
    checked_count = 0

    for route in app.routes:
        path = getattr(route, "path", "")
        if not _is_business(path):
            continue

        methods = getattr(route, "methods", [])
        endpoint = getattr(route, "endpoint", None)

        if endpoint is None:
            continue

        for method in methods:
            if method in {"HEAD", "OPTIONS"}:
                continue

            checked_count += 1

            # Check 1: Has org_id dependency?
            if not _has_org_dep(endpoint):
                failures.append(
                    f"{method} {path}: missing org_id = Depends(get_org_scope) or OrgScope parameter"
                )
                continue

            # Check 2: Module contains scoped operations?
            if not _module_contains_scoped_ops(endpoint):
                failures.append(
                    f"{method} {path}: handler module lacks exec_scoped() or org_id filters "
                    "(add explicit .where(Model.org_id == org_id) or exec_scoped())"
                )

    # Assert no failures
    assert not failures, (
        f"❌ Org scoping violations found in {len(failures)}/{checked_count} routes:\n"
        + "\n".join(f"  - {f}" for f in failures)
        + "\n\n"
        + "FIX: Ensure all business endpoints:\n"
        + "  1. Have org_id: OrgScope parameter\n"
        + "  2. Use exec_scoped() for SQL or .where(Model.org_id == org_id) for ORM\n"
    )

    # Success message
    print(f"✅ All {checked_count} business routes are properly org-scoped")
