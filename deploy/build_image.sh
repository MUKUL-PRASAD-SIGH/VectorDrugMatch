#!/usr/bin/env bash
# deploy/build_image.sh <bundle_dir> - build vectordrugmatch-api:<bundle version> from a minimal context. Verifies bundle checksums first.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
B="$(cd "$1" && pwd)"
VER="$(python -c "import json,sys;print(json.load(open(sys.argv[1]))['bundle_version'])" "$B/manifest.json")"
python - "$B" <<'PY'
import hashlib, json, sys, pathlib
b = pathlib.Path(sys.argv[1]); m = json.loads((b / "manifest.json").read_text())
bad = [n for n, h in m["files_sha256"].items() if hashlib.sha256((b / n).read_bytes()).hexdigest() != h]
sys.exit(f"checksum mismatch: {bad}") if bad else print("bundle checksums OK:", m["bundle_version"], m["status"])
PY
CTX="$(mktemp -d)"; trap 'rm -rf "$CTX"' EXIT
mkdir -p "$CTX/src/features" "$CTX/src/serving"
cp "$REPO/src/__init__.py" "$CTX/src/"
cp "$REPO/src/features/__init__.py" "$REPO/src/features/simple_baselines.py" "$REPO/src/features/disease_profile.py" "$CTX/src/features/"
cp "$REPO/src/serving/"*.py "$CTX/src/serving/"
cp "$REPO/requirements-serving.lock" "$REPO/deploy/Dockerfile" "$CTX/"
cp -r "$B" "$CTX/bundle"
docker build -t "vectordrugmatch-api:$VER" "$CTX"
echo "built vectordrugmatch-api:$VER"
