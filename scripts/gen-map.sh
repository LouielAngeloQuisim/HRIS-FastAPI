#!/usr/bin/env bash
#
# scripts/gen-map.sh - generate docs/MAP.md, a live architecture map of the
# backend and frontend, derived from the actual code (not hand-written).
#
# Extracts, without running any server:
#   1. FastAPI routes (+ per-route RBAC permissions where declared) by
#      importing app.main and walking each route's dependant tree.
#   2. backend/app/<domain>/ packages and which layer files they contain.
#   3. frontendv3 features, which @/lib/api modules they import, and whether
#      they have a route dir / form component / colocated Vitest file.
#      (Single-line imports make grep-based extraction reliable; verified
#      against the src tree in the session this script was written in.)
#   4. the alembic revision chain, parsed statically from version files.
#   5. cheap cross-reference: backend domains whose name also exists as a
#      frontend feature.
#
# Read-only w.r.t. the codebase: the only file it writes is docs/MAP.md.
# Set MAP_OUT=/path/to/file to redirect output (verify.sh uses this for the
# report-only drift check and never lets the committed map be modified).
#
# Usage: bash scripts/gen-map.sh   (from anywhere; it resolves the repo root)

set -eu
set -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${MAP_OUT:-$ROOT/docs/MAP.md}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Importing app.main constructs Settings, which requires several env vars.
# Exported vars win over any repo-root .env (same trick scripts/verify.sh uses),
# so this works on a fresh checkout with no .env and can never touch a real DB:
# no engine connect() happens at import time and no server is started.
export ENVIRONMENT=local
export PROJECT_NAME="${PROJECT_NAME:-HRIS}"
export SECRET_KEY="${SECRET_KEY:-gen-map-placeholder-not-a-real-secret}"
export FIRST_SUPERUSER="${FIRST_SUPERUSER:-admin@example.com}"
export FIRST_SUPERUSER_PASSWORD="${FIRST_SUPERUSER_PASSWORD:-gen-map-only}"
export EMAILS_FROM_EMAIL="${EMAILS_FROM_EMAIL:-info@example.com}"
export POSTGRES_USER="${POSTGRES_USER:-genmap}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-genmap}"
export POSTGRES_DB="${POSTGRES_DB:-genmap}"
export POSTGRES_SERVER="${POSTGRES_SERVER:-127.0.0.1}"
export POSTGRES_PORT="${POSTGRES_PORT:-55998}"

# ------------------------------------------------- step 1: routes + permissions
(
  cd "$ROOT/backend"
  uv run python - "$TMP/routes.json" <<'PYEOF'
import json
import sys

from app.main import app
from app.rbac.dependencies import PermissionChecker


def find_checkers(dep):
    out = []
    call = getattr(dep, "call", None)
    if isinstance(call, PermissionChecker):
        out.append([call.module, call.action.value])
    for sub in getattr(dep, "dependencies", []):
        out.extend(find_checkers(sub))
    return out


routes = []
for r in app.routes:
    if not hasattr(r, "methods") or not r.path.startswith("/api"):
        continue
    perms = sorted({tuple(p) for p in find_checkers(getattr(r, "dependant", None))}) if hasattr(r, "dependant") else []
    routes.append({
        "path": r.path,
        "methods": sorted(m for m in r.methods if m not in ("HEAD", "OPTIONS")),
        "perms": [f"{m}:{a}" for m, a in perms],
    })

with open(sys.argv[1], "w") as fh:
    json.dump(routes, fh)
print(f"extracted {len(routes)} /api routes", file=sys.stderr)
PYEOF
)

# ---------------------------------------- steps 2-5 + assembly of docs/MAP.md
python3 - "$ROOT" "$TMP/routes.json" "$OUT" <<'PYEOF'
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

root, routes_json, out_path = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])

commit = subprocess.run(
    ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
    capture_output=True, text=True, check=True,
).stdout.strip()

routes = json.loads(routes_json.read_text())

# -- section: routes grouped by /api/v1/<group> -------------------------------
groups: dict[str, list[dict]] = {}
for row in routes:
    parts = row["path"].strip("/").split("/")
    key = "/" + "/".join(parts[:3]) if len(parts) > 2 else "/api"
    groups.setdefault(key, []).append(row)

# -- section: backend domain packages -----------------------------------------
# Layer "files" include routes sub-packages (item/routes/, user/routes/) where
# the package instead of a single routes.py file implements the layer.
LAYERS = ["models.py", "schemas.py", "routes.py", "services.py", "selectors.py"]
SKIP = {"__pycache__", "config", "email-templates", "common"}
domains = []
for d in sorted(p for p in (root / "backend" / "app").iterdir() if p.is_dir() and p.name not in SKIP):
    present = []
    for f in LAYERS:
        if (d / f).is_file():
            present.append(f)
        elif (d / f.removesuffix(".py")).is_dir():
            present.append(f.removesuffix(".py") + "/")
    if present:
        domains.append((d.name, present))

# -- section: frontend features ------------------------------------------------
api_ref = re.compile(r"@/lib/api/([A-Za-z0-9_-]+)")
features = []
feat_root = root / "frontendv3" / "src" / "features"
for fd in sorted(p for p in feat_root.iterdir() if p.is_dir() and p.name not in {"shared", "errors"}):
    ts_files = [p for p in fd.rglob("*") if p.suffix in (".ts", ".tsx") and p.is_file()]
    if not ts_files:
        continue  # empty dir, not a feature
    apis: set[str] = set()
    for p in ts_files:
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for m in api_ref.finditer(text):
            mod = m.group(1)
            if mod not in ("client", "types"):
                apis.add(mod)
    has_route = (root / "frontendv3" / "src" / "routes" / "_authenticated" / fd.name).is_dir()
    has_form = any(
        p.name.endswith("form.tsx") and not p.name.endswith(".test.tsx")
        for p in ts_files
    )
    has_test = any(p.name.endswith((".test.tsx", ".test.ts")) for p in ts_files)
    features.append((fd.name, sorted(apis), has_route, has_form, has_test))

# -- section: migration chain --------------------------------------------------
def parse_migrations(backend_dir: Path):
    revs: dict[str, tuple[str | None, str, str]] = {}
    for f in sorted((backend_dir / "alembic" / "versions").glob("*.py")):
        t = f.read_text(encoding="utf-8", errors="replace")
        r = re.search(r"^revision\b[^=]*=\s*['\"]([^'\"]+)", t, re.M)
        dn = re.search(r"^down_revision\b[^=]*=\s*(?:['\"]([^'\"]+)['\"]|None)", t, re.M)
        desc = t.splitlines()[0].strip().strip('"').strip("'")
        if r:
            revs[r.group(1)] = (dn.group(1) if dn and dn.group(1) else None, f.name, desc)
    downs = {v[0] for v in revs.values() if v[0]}
    heads = sorted(k for k in revs if k not in downs)
    chain: list[tuple[str, str, str]] = []
    if len(heads) == 1:
        cur: str | None = heads[0]
        seen: set[str] = set()
        while cur and cur in revs and cur not in seen:
            seen.add(cur)
            down, fn, desc = revs[cur]
            chain.append((cur, fn, desc))
            cur = down
        chain.reverse()
    return revs, heads, chain

revs, heads, chain = parse_migrations(root / "backend")

# -- section: cross-reference match ---------------------------------------------
feat_names = {name for name, *_ in features}
matched_pairs = sorted(d for d, _ in domains if d in feat_names)

# =================================================================================
lines: list[str] = []
add = lines.append

add("# Architecture Map (generated, do not hand-edit)")
add(f"Generated: {date.today().isoformat()}, from commit {commit}")
add("Regenerate this file with `bash scripts/gen-map.sh` rather than editing it by hand.")
add("")
add(f"## Backend routes (`/api/*`): {len(routes)} endpoints in {len(groups)} groups")
add("")
add("Grouped by top-level prefix. Format: `METHOD path  [perms: module:action]`.")
add("No `[perms]` tag means the route has no `require_permission` dependency:")
add("either auth/public endpoints, template demo resources (items, login flow),")
add("or routes protected by the route_policy whitelist instead of RBAC modules.")
add("")
for g in sorted(groups):
    add(f"### `{g}` ({len(groups[g])} routes)")
    add("")
    for row in sorted(groups[g], key=lambda r: (r["path"], r["methods"])):
        methods = ",".join(row["methods"])
        perms = f"  `[perms: {', '.join(row['perms'])}]`" if row["perms"] else ""
        add(f"- `{methods} {row['path']}`{perms}")
    add("")

add(f"## Backend domain packages (`backend/app/`): {len(domains)} domains")
add("")
add("Layer files present per package. `backend/app/common/` holds shared infra and")
add("is omitted here, as are `config` (engine/settings) and `email-templates`.")
add("")
for name, present in domains:
    add(f"- `{name}`: {', '.join(present) if present else '(no standard layer files)'}")
add("")

add(f"## Frontend features (`frontendv3/src/features/`): {len(features)} features")
add("")
add("API columns are modules imported from `@/lib/api/*` (grep-based, per-verified")
add("reliable in the source tree's single-line import style) with plumbing")
add("(`client`/`types`) excluded. Flags: `route` = matching dir under")
add("`src/routes/_authenticated/`, `form` = a `*form.tsx` component exists,")
add("`test` = a colocated Vitest file exists.")
add("")
for name, apis, has_route, has_form, has_test in features:
    flaglist = []
    if has_route:
        flaglist.append("route")
    if has_form:
        flaglist.append("form")
    if has_test:
        flaglist.append("test")
    flags = ", ".join(flaglist) if flaglist else "(none)"
    apis_txt = ", ".join(f"`{a}`" for a in apis) if apis else "`none`"
    add(f"- `{name}`: api {apis_txt}; flags: {flags}")
add("")

if chain:
    add(f"## Migration chain (oldest -> newest): {len(chain)} revisions, single head `{heads[0]}`")
    add("")
    add("Parsed statically from `backend/alembic/versions/*.py` (`revision` /")
    add("`down_revision` tokens); no `alembic history` subprocess required.")
    add("")
    for i, (rev, fn, desc) in enumerate(chain, 1):
        add(f"{i}. `{rev}` - {desc}")
else:
    add("## Migration chain")
    add("")
    add(f"COULD NOT RESOLVE a linear chain: {len(revs)} revision files found,")
    add(f"heads = {heads or 'none'}. Inspect with `cd backend && alembic history` instead.")
add("")

add("## Cross-reference: backend domain <-> frontend feature (exact name match)")
add("")
add("The cheapest signal for which frontend screens talk to which backend module.")
add("Name-only match: the frontend feature and the app/ package with the same")
add("basename. Does not replace reading the actual imports for a given feature.")
add("")
if matched_pairs:
    for d in matched_pairs:
        add(f"- `{d}` <-> `{d}`")
else:
    add("(no exact name matches - which would be surprising; verify manually)")
add("")
unmatched_backend = [d for d, _ in domains if d not in feat_names]
unmatched_frontend = [name for name, *_ in features if name not in {d for d, _ in domains}]
add("Backend domains with no same-named frontend feature: " +
    (", ".join(f"`{d}`" for d in unmatched_backend) if unmatched_backend else "none"))
add("(A name mismatch here does not mean the domain is unused: `app/employee/` serves")
add("routers for ~16 resources that each have their own frontend feature, and")
add("`attendance`/`leave`/`rbac` back multiple differently-named feature screens.)")
add("")
add("Frontend features with no same-named backend domain: " +
    (", ".join(f"`{f}`" for f in unmatched_frontend) if unmatched_frontend else "none"))
add("(Many map to a differently-named backend domain, e.g. all `leave-*`/`holidays`")
add("features hit `app/leave/`, and the CRUD screens under `app/employee/`;")
add("`apps`/`chats`/`tasks`/`settings`/`users` are unwired template-demo features.)")
add("")

out_path.write_text("\n".join(lines))
print(f"wrote {out_path} ({len(lines)} lines, {len(routes)} routes, {len(domains)} domains, "
      f"{len(features)} features, chain={len(chain)} revisions)", file=sys.stderr)
PYEOF
