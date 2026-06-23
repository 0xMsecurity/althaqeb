#!/usr/bin/env bash
# Cross-version bisection for ChromaDB residue. Creates an isolated venv per version,
# installs chromadb==X, runs probe.py, collects one PROBE_JSON line each.
# Heavy installs go under build/ (gitignored); cleaned at the end.
set -u
cd "$(dirname "$0")/.."
ROOT="$PWD"
VENVDIR="$ROOT/build/xver_venvs"; mkdir -p "$VENVDIR"
OUT="$ROOT/results/cross_version_chroma.jsonl"; : > "$OUT"
VERSIONS="${*:-0.4.24 0.5.0 0.5.23 0.6.3 1.0.21 1.3.7 1.5.9}"
for V in $VERSIONS; do
  echo "===== chromadb==$V ====="
  VE="$VENVDIR/v$V"
  python3 -m venv "$VE" 2>/dev/null
  if ! "$VE/bin/python" -m pip install -q "chromadb==$V" numpy 2>"$VENVDIR/pip_$V.err"; then
    echo "PROBE_JSON {\"version\":\"$V\",\"install\":\"FAILED\",\"err\":\"$(tail -1 "$VENVDIR/pip_$V.err" 2>/dev/null | tr -d '"' | cut -c1-160)\"}" | tee -a "$OUT"
    rm -rf "$VE"; continue
  fi
  LINE=$("$VE/bin/python" "$ROOT/cross_version/probe.py" "$ROOT/build/xver_db_$V" 2>/dev/null | grep '^PROBE_JSON')
  if [ -z "$LINE" ]; then LINE="PROBE_JSON {\"version\":\"$V\",\"run\":\"FAILED\"}"; fi
  echo "$LINE" | tee -a "$OUT"
  rm -rf "$VE" "$ROOT/build/xver_db_$V"
done
echo "===== summary ====="; sed 's/^PROBE_JSON //' "$OUT"
