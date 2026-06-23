#!/usr/bin/env bash
# Re-hash artifacts and verify against MANIFEST.sha256 (chain of custody / tamper check).
# Exit 0 = all match, 2 = mismatch/missing.
set -u
cd "$(dirname "$0")"
if [ ! -f MANIFEST.sha256 ]; then echo "MANIFEST.sha256 missing"; exit 2; fi
grep -v '^#' MANIFEST.sha256 | sha256sum -c --quiet
rc=$?
if [ $rc -eq 0 ]; then echo "[OK] all $(grep -vc '^#' MANIFEST.sha256) artifacts match manifest"; else echo "[FAIL] manifest mismatch (rc=$rc)"; fi
exit $rc
