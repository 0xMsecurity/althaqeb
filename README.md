# althaqeb — vector-store erasure-durability research, tooling & standard

Does **`delete()` actually erase?** Althaqeb studies whether logically-deleted embedding
vectors ever leave an agent / vector-database memory store — and turns the surviving
evidence into durable, reusable assets.

> **Finding (executed, not asserted):** After an official `delete()` that the logical layer
> reports as clean — and after plaintext / write-ahead-log residue is purged by compaction —
> the embedding vector retained in the ANN index (e.g. HNSW `data_level0.bin`) is still
> **bit-identical recoverable** from disk, the engine's own metadata often **self-identifies**
> which vectors were deleted, and the recovered vector **inverts back to its original text**
> (vec2text). A post-delete recovery window exists in every real engine tested; it is
> **unbounded only on ChromaDB**.

Every claim here is traceable to a committed script + result JSON + log. Negative results are
kept, not hidden. A build gate (`build_matrix.py`) **fails** if any published claim loses its
evidence file — NO FAKE RESULTS is enforced mechanically, not promised.

## The layers (research → tool → registry → standard)

This repo is built as a ladder; each rung is grounded in the one below it:

| Layer | Artifact | What it gives you |
|---|---|---|
| **Experiments** | [`experiments/residue/`](experiments/residue/) | 18 phases × real engines, committed results + logs |
| **Tool** | [`experiments/residue/tool/vdbresidue.py`](experiments/residue/tool/) | read-only DFIR / GDPR-erasure auditor (exit 2 = residue found) |
| **Registry** | [`benchmarks/deletion-durability/`](benchmarks/deletion-durability/) | evidence-traceable comparison matrix across 8 engines |
| **Standard (draft)** | [`standards/erasure-durability/`](standards/erasure-durability/) | **VEDC** — a classification of erasure durability + an executable conformance tool |

## Start here

| File | What it is |
|---|---|
| [`STATE.md`](STATE.md) | Self-contained state of record — read this first. |
| [`PRINCIPLES.md`](PRINCIPLES.md) | How decisions are made — principles & method (North Star, 14 review lenses, Reality has veto). |
| [`GRAVEYARD.md`](GRAVEYARD.md) | Dead directions + why. Read before proposing anything new. |
| [`benchmarks/deletion-durability/MATRIX.md`](benchmarks/deletion-durability/MATRIX.md) | The cross-engine durability matrix (generated). |
| [`standards/erasure-durability/SPEC.md`](standards/erasure-durability/SPEC.md) | The VEDC classification spec + `CLASSIFICATION.md` roster. |
| [`SECURITY.md`](SECURITY.md) | Responsible-disclosure policy. |

## The headline matrix

A post-delete recovery window is **universal**; its duration is **unbounded only on ChromaDB**.
Generated from `registry.json`, every cell evidence-backed:

| Window class | Engines |
|---|---|
| **VEDC-U — unbounded** (no reclamation observed) | ChromaDB `+S` |
| auto / untimed (optimizer, autovacuum) | Qdrant-server, pgvector index |
| manual-only (VACUUM FULL) | Postgres heap `+S` |
| auto / timed | Weaviate (~70s), Milvus (~360s) `+S` |
| none — no residue (true negatives) | FAISS, Qdrant-local |

`+S` = deletion self-identifies the residue. Only ChromaDB's classification is **Confirmed**
(multi-seed + cross-version); the rest are **Provisional** (single trajectory) — multi-seed
replication is the named next experiment.

## The tool

`experiments/residue/tool/vdbresidue.py` — read-only, deterministic, no-LLM DFIR / GDPR-erasure
auditor. Detects and recovers vectors a database reports as deleted but still leaves physically
recoverable on disk. Streams in bounded memory (runs on multi-GB stores). Exit code 2 =
recoverable residue found.

```bash
cd experiments/residue
python3 -m venv .venv && .venv/bin/pip install -r requirements.lock.txt
.venv/bin/python tool/selftest.py        # deterministic, ~5s, no downloads -> SELFTEST PASS
.venv/bin/python tool/vdbresidue.py report <chroma_or_milvus_db_path>
```

## Reproduce

```bash
# experiments + tool
cd experiments/residue
./verify_manifest.sh        # chain-of-custody over the evidence tree (66 artifacts)
./run_all.sh cpu            # CPU-only phases
./run_all.sh docker         # engine phases requiring docker (qdrant/weaviate/milvus)

# registry + standard integrity (stdlib only, no deps) — same gate CI runs
cd ../..
python3 benchmarks/deletion-durability/build_matrix.py --check
python3 standards/erasure-durability/classify.py --check
```

`.venv/`, `hf_cache/`, `db/`, `build/` are reproducible-from-scratch and git-ignored;
`results/` and `logs/` are committed evidence. CI
([`.github/workflows/registry-integrity.yml`](.github/workflows/registry-integrity.yml))
re-runs both gates on every push.

## Status

- **Engines:** ChromaDB, Milvus (standalone), Qdrant (server), Weaviate, pgvector (index +
  heap), Postgres heap — plus FAISS / Qdrant-local as clean negatives.
- **Experiments:** saturated. Now in registry/standard hardening; next experiment = multi-seed
  replication to upgrade Provisional → Confirmed.
- **Disclosure:** drafts ready under `experiments/residue/disclosure/`, **not sent** (human gate).

## Ethics

These experiments recover *synthetic* poison and test PII only. The same capability can recover
*deleted user data* — treat it as **dual-use**. The tooling is read-only and built for the
defensive case (verifying an erasure actually removed data). The VEDC method has a documented
quantization blind spot (SPEC §9) — "no float32 residue" is not "no recoverable residue".
See `SECURITY.md`; disclosure is coordinated and gated on human approval.
