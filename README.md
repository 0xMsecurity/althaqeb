# althaqeb — vector-database deletion-residue forensics

Research code and a forensic tool for studying whether **"deletion is erasure"** in
LLM-agent / vector-database memory stores.

> **Finding (executed, not asserted):** After an official `delete()` that the logical
> layer reports as clean — and after plaintext / write-ahead-log residue is purged by
> compaction — the embedding vector retained inside the ANN index (e.g. HNSW
> `data_level0.bin`) is still **bit-identical recoverable** from disk, the engine's own
> metadata often **self-identifies** which vectors were deleted, and the recovered vector
> **inverts back to its original text** (vec2text). A post-delete recovery window is
> universal across the 6 real engines tested; it is **unbounded only on ChromaDB**.

This repo contains **only executed experiments and their raw observations**. No claim
appears that is not traceable to a script in `experiments/residue/scripts/`, a JSON in
`experiments/residue/results/`, and a log in `experiments/residue/logs/`. Negative
results are kept, not hidden.

## Start here

| File | What it is |
|---|---|
| [`STATE.md`](STATE.md) | Self-contained state of record — read this first. |
| [`GRAVEYARD.md`](GRAVEYARD.md) | Dead directions + why. Read before proposing anything new. |
| [`experiments/residue/FINDINGS.md`](experiments/residue/FINDINGS.md) | Every surviving claim with per-claim evidence. |
| [`experiments/residue/tool/README.md`](experiments/residue/tool/README.md) | The `vdbresidue` forensic tool. |
| [`SECURITY.md`](SECURITY.md) | Responsible-disclosure policy. |

## The tool

`experiments/residue/tool/vdbresidue.py` — read-only, deterministic, no-LLM DFIR /
GDPR-erasure auditor. Detects and recovers vectors a database reports as deleted but
still leaves physically recoverable on disk. Exit code 2 = recoverable residue found.

```bash
cd experiments/residue
python3 -m venv .venv && .venv/bin/pip install -r requirements.lock.txt
.venv/bin/python tool/selftest.py        # deterministic, ~5s, no downloads -> SELFTEST PASS
.venv/bin/python tool/vdbresidue.py report <chroma_or_milvus_db_path>
```

## Reproduce the experiments

```bash
cd experiments/residue
./verify_manifest.sh        # chain-of-custody check over the evidence tree
./run_all.sh cpu            # CPU-only phases
./run_all.sh docker         # engine phases requiring docker (qdrant/weaviate/milvus)
```

Pinned in `experiments/residue/requirements.lock.txt`; environment recorded in
`experiments/residue/results/ENV.txt`. `.venv/`, `hf_cache/`, `db/`, `build/` are
reproducible-from-scratch and git-ignored; `results/` and `logs/` are committed evidence.

> The five scripts in `experiments/` (`01_…`–`05_…`) are the original gate experiments,
> superseded by the `phase1`–`phase18` tree under `experiments/residue/scripts/`. They
> are retained as history.

## Status

- **Engines tested:** ChromaDB, Milvus (standalone), Qdrant (server), Weaviate, pgvector
  (index + heap), Postgres heap — plus FAISS / Qdrant-local as clean negatives.
- **Experiments:** saturated. Project is in implementation / hardening / packaging.
- **Disclosure:** drafts ready under `experiments/residue/disclosure/`, **not sent**
  (human approval gate).

## Ethics

These experiments recover *synthetic* poison and synthetic test PII only. The same
residue-recovery capability can recover *deleted user data* — treat it as dual-use. The
tool is read-only and built for the defensive case (verifying that an erasure actually
removed data). See `SECURITY.md`. Disclosure to affected projects is coordinated and
gated on human approval.
