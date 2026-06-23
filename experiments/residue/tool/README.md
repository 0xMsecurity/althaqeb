# vdbresidue — deleted-vector residue forensic auditor

Read-only, deterministic, no-LLM tool that detects and recovers embedding vectors a vector
database reports as deleted but still leaves physically recoverable on disk.

## Why
Vector DBs delete *logically* (tombstone / mark-deleted); physical reclamation is deferred
to a compaction/vacuum that often does not run for small (e.g. right-to-be-forgotten)
deletions. The deleted vector — bit-identical and invertible to its source text — remains on
disk and is frequently *self-identified* as deleted by the engine's own metadata. This tool
lets a data controller or DFIR analyst verify whether an erasure actually removed data.

## Guarantees
- **Read-only** on the target DB (opens files `rb`; never writes/mutates the source).
- **Deterministic**: no randomness, no network, no model/LLM. Pure file parsing.
- **Chain of custody**: every operation appends a JSONL record (`vdbresidue_coc.jsonl`)
  with UTC timestamp, target, output file SHA256s, and result counts.

## Backends
Two recovery modes, by what the engine's on-disk format makes possible:

**Blind recovery** (recovers deleted vectors with no prior knowledge — deletion self-identifies):
| Backend | "which are deleted" | Recovery |
|---|---|---|
| `chroma` | DUAL signal w/ precedence (0 false positives): (1) hnswlib `DELETE_MARK` bit (byte +2) once compaction has re-persisted the segment; (2) when no marks are present (low-post-delete-write state), segment label ∉ live `seq_id` set in `chroma.sqlite3` (`embeddings` table). Marks take precedence because post-compaction labels ≠ seq_ids. dims from `header.bin`. | blind, exact |
| `milvus` | `delta/*.parquet` tombstone ids ∩ segment `data/*.parquet` | blind, exact |

The chroma dual-signal closes a real blind spot: immediately after a delete with few subsequent
writes, the `DELETE_MARK` bit is not yet written to the segment (the delete lives in
`chroma.sqlite3`), yet the vector is physically present — the sqlite-orphan signal recovers it
(validated `../scripts/phase17_tool_blindspot_validation.py`, 0 false positives).

**Match mode** (`match`) — deterministic exact-byte presence check for KNOWN target vectors;
works on **every** engine (chroma/milvus/qdrant/weaviate/pgvector/any), zero false positives.
Use when you have candidate sensitive vectors and ask "did this survive deletion on disk?".
For Qdrant/Weaviate, deleted-vs-live is not blind-separable from raw files, so `match` is the
rigorous path (no noisy carving). Detection of `qdrant`/`weaviate` is supported for routing.

## Usage
```
python vdbresidue.py inspect <db_path>              # identify backend + deleted count
python vdbresidue.py recover <db_path> --out DIR    # extract deleted vectors -> .npy + index.json
python vdbresidue.py report  <db_path> [--out F]    # markdown/JSON forensic report + verdict
python vdbresidue.py acquire <db_path> --out BUNDLE # copy raw evidence + SHA256 manifest (CoC)
python vdbresidue.py match   <db_path> --vectors T.npy  # exact-byte presence of known vectors (any engine)
python vdbresidue.py verify  <MANIFEST.sha256>      # tamper-check a manifest
```
Exit code: **2** if recoverable deleted residue is found (CI/erasure gate), 0 if clean, 1 on error.

## Self-test (deterministic, ~5s, no downloads)
```
python selftest.py     # builds a tiny Chroma DB, deletes 7, asserts exact recovery -> PASS
```

## Validated
Chroma + Milvus backends recover deleted vectors at cosine 1.0 / bit-identical against known
originals (`../scripts/phase6`, `phase7`, this `selftest.py`). Recovered vectors are
invertible to text via `vec2text` (see `../scripts/phase1`) — intentionally a separate,
optional step so this tool stays dependency-light and deterministic.

## Limitations
- Recovers what is physically present at scan time; after a successful compaction/vacuum/GC
  that reclaims the segment, residue may be gone (engine- and config-dependent — see FINDINGS).
- `chroma` dim detection prefers `header.bin`; falls back to size-inference (maxM0=32).
- `milvus` requires `pyarrow` to read parquet segments.
