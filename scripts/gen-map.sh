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
#   4. the alembic revision chain, parsed statically from version files, plus a
#      report-only static anomaly scan (empty upgrades, duplicated constraint
#      signatures, description/body mismatches, enum types without downgrade
#      cleanup). Findings are generated from source text, never hard-coded.
#   5. cheap cross-reference: backend domains whose name also exists as a
#      frontend feature.
#
# Read-only w.r.t. the codebase: the only file it writes is docs/MAP.md.
# Set MAP_OUT=/path/to/file to redirect output (verify.sh uses this for the
# report-only drift check and never lets the committed map be modified).
#
# Usage: bash scripts/gen-map.sh [SOURCE_COMMIT]   (from anywhere; resolves repo root)
#
#   SOURCE_COMMIT: git revision to record as the provenance of the generated
#   content (e.g. a tag or sha). Defaults to the current HEAD. The recorded
#   commit is the repository STATE the content was extracted from; when the
#   regenerated file is itself committed, the commit storing it is a DESCENDANT
#   of the recorded commit, and that distinction is stated in the header
#   instead of being silently conflated.
#   Extraction always reads the current working tree; pass an explicit
#   SOURCE_COMMIT only when that tree genuinely represents that commit.
#   An unknown revision is a hard error: the generator never invents or
#   silently substitutes a source commit.

set -eu
set -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${MAP_OUT:-$ROOT/docs/MAP.md}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

SRC_REF="${1:-HEAD}"
SRC_SHA="$(git -C "$ROOT" rev-parse --verify "${SRC_REF}^{commit}")" || {
  echo "gen-map.sh: not a valid source commit: ${SRC_REF}" >&2
  exit 2
}
export MAP_SOURCE_COMMIT="$SRC_SHA"

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
import sys
from datetime import date
from pathlib import Path

root, routes_json, out_path = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])

src_commit = os.environ["MAP_SOURCE_COMMIT"]

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

# -- section: migration chain + static anomaly scan ----------------------------
def extract_func(text: str, name: str) -> str | None:
    m = re.search(rf"^def {name}\b[^\n]*:\n", text, re.M)
    if not m:
        return None
    body_start = m.end()
    lines = text[body_start:].splitlines()
    out: list[str] = []
    for ln in lines:
        if ln.strip() and not ln.startswith((" ", "\t", "#")):
            break
        out.append(ln)
    return "\n".join(out)


OP_CALL = re.compile(r"^\s*op\.(\w+)\(", re.M)


def op_calls(body: str) -> list[str]:
    return [m.group(1) for m in OP_CALL.finditer(body)]


def op_call_texts(body: str) -> list[str]:
    """Full text of each top-level op.* call (args included, balanced parens)."""
    out: list[str] = []
    for m in re.finditer(r"op\.(\w+)\(", body):
        depth, i = 1, m.end()
        while i < len(body) and depth:
            if body[i] == "(":
                depth += 1
            elif body[i] == ")":
                depth -= 1
            i += 1
        out.append(body[m.start():i])
    return out


def normalized_body(body: str) -> str:
    """Comment-stripped, whitespace-normalized, sorted op-call sequence."""
    cleaned = []
    for call in op_call_texts(body):
        call = re.sub(r"#.*", "", call)
        call = re.sub(r"\s+", "", call)
        if call:
            cleaned.append(call)
    if not cleaned:
        return ""
    return "|".join(sorted(cleaned))


ENUM_CREATE = re.compile(r"sa\.Enum\((?:[^()]|\([^()]*\))*?name=['\"]([^'\"]+)['\"]", re.S)
ENUM_DROP = re.compile(r"DROP TYPE\s+([A-Za-z_][A-Za-z0-9_]*)", re.I)
CREATE_TABLE = re.compile(r"op\.create_table\(\s*['\"]([^'\"]+)['\"]")
# Heuristic for (c), deliberately narrow: only the PLURAL word "tables" counts as a
# promise of table creation, matched after a space or an identifier underscore
# ("holiday tables" and "add_payroll_tables" both match). This avoids unrelated
# singular-word collisions such as "add missing payroll table indexes", an
# index-only migration where "table" modifies "indexes", not a create promise.
DESC_TABLE_HINT = re.compile(r"(?:[\s_])tables\b", re.I)

def parse_migrations(backend_dir: Path):
    revs: dict[str, tuple[str | None, str, str]] = {}
    bodies: dict[str, tuple[str, str]] = {}
    for f in sorted((backend_dir / "alembic" / "versions").glob("*.py")):
        t = f.read_text(encoding="utf-8", errors="replace")
        r = re.search(r"^revision\b[^=]*=\s*['\"]([^'\"]+)", t, re.M)
        dn = re.search(r"^down_revision\b[^=]*=\s*(?:['\"]([^'\"]+)['\"]|None)", t, re.M)
        desc = t.splitlines()[0].strip().strip('"').strip("'")
        if r:
            revs[r.group(1)] = (dn.group(1) if dn and dn.group(1) else None, f.name, desc)
            up = extract_func(t, "upgrade") or ""
            dg = extract_func(t, "downgrade") or ""
            bodies[r.group(1)] = (up, dg)
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
    return revs, heads, chain, bodies


def detect_anomalies(revs, bodies):
    """Static, report-only findings; all lists sorted by revision for determinism."""
    findings: list[str] = []

    # (a) empty upgrade: no op.* call at all in upgrade()
    empty_up = sorted(
        rev for rev in revs
        if rev in bodies and not op_calls(bodies[rev][0])
    )
    for rev in empty_up:
        findings.append(
            f"- `{rev}` ({revs[rev][2]}): `upgrade()` contains no `op.*` call "
            "(effectively a no-op migration; its child may carry the intended work)"
        )

    # (b) duplicated normalized constraint-change signatures between revisions
    sig_map: dict[str, list[str]] = {}
    for rev in sorted(bodies):
        up = bodies[rev][0]
        if not up.strip():
            continue
        sig = normalized_body(up)
        if sig and "constraint" in sig:
            sig_map.setdefault(sig, []).append(rev)
    dup_groups = sorted(
        (tuple(sorted(revs_)) for sig, revs_ in sig_map.items() if len(revs_) > 1)
    )
    for group in dup_groups:
        findings.append(
            "- " + ", ".join(f"`{r}` ({revs[r][2]})" for r in group)
            + ": identical normalized `upgrade()` constraint-operation signature"
        )

    # (c) description promises table creation but upgrade() has no create_table.
    # Heuristic (documented, deliberately conservative): only flags revisions
    # whose first-line description matches DESC_TABLE_HINT (plural "tables" after
    # a space/underscore) AND whose upgrade() actually runs op.* calls yet
    # contains no op.create_table. Revisions with an empty upgrade() are reported
    # under (a) instead, and descriptions merely containing the singular word
    # "table" (e.g. "payroll table indexes") are not flagged.
    for rev in sorted(revs):
        desc = revs[rev][2]
        if not DESC_TABLE_HINT.search(desc):
            continue
        up = bodies.get(rev, ("", ""))[0]
        if not up.strip() or CREATE_TABLE.search(up):
            continue
        if not op_calls(up):
            continue  # already reported as empty-upgrade (a); don't double-report
        findings.append(
            f"- `{rev}` ({desc}): description mentions table creation but "
            "`upgrade()` contains no `op.create_table` call"
        )

    # (d) sa.Enum types created in upgrade() with no DROP TYPE in same downgrade()
    for rev in sorted(revs):
        up, dg = bodies.get(rev, ("", ""))
        created = sorted({m.group(1) for m in ENUM_CREATE.finditer(up)})
        if not created:
            continue
        dropped = {m.group(1).lower() for m in ENUM_DROP.finditer(dg)}
        missing = [c for c in created if c.lower() not in dropped]
        if missing:
            findings.append(
                f"- `{rev}` ({revs[rev][2]}): creates native enum type(s) "
                + ", ".join(f"`{m}`" for m in missing)
                + " in `upgrade()` with no matching `DROP TYPE` in its `downgrade()` "
                "(downgrade leaves the postgres type orphaned; enum cleanup would "
                "need a follow-up migration or explicit ops runbook)"
            )

    return findings


revs, heads, chain, bodies = parse_migrations(root / "backend")

# -- section: cross-reference match ---------------------------------------------
feat_names = {name for name, *_ in features}
matched_pairs = sorted(d for d, _ in domains if d in feat_names)

# =================================================================================
lines: list[str] = []
add = lines.append

add("# Architecture Map (generated, do not hand-edit)")
add(f"Generated: {date.today().isoformat()}")
add(f"Source commit: {src_commit}")
add("Provenance: the content below was extracted from the working tree at the")
add("Source commit shown. When this file is itself committed, the commit that")
add("stores it is a DESCENDANT of the Source commit, not the Source commit.")
add("Regenerate this file with `bash scripts/gen-map.sh [SOURCE_COMMIT]`")
add("rather than editing it by hand.")
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

anomalies = detect_anomalies(revs, bodies)
add("### Migration anomalies (static findings, report-only)")
add("")
add("Derived by `scripts/gen-map.sh` from the migration source text only. These")
add("are NOT defects proven by running anything: each needs human review before")
add("any action. Historical migration files are never modified by the generator.")
add("")
if anomalies:
    add(f"{len(anomalies)} finding(s):")
    add("")
    for line in anomalies:
        add(line)
else:
    add("No static anomalies detected.")
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
