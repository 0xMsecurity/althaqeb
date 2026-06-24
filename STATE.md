# ALTHAQEB — STATE OF RECORD

> Self-contained continuity snapshot. If every other context (chat history, external
> memory, the people) disappeared, this file plus the artifacts it points to must be
> enough for a stranger to understand what was done, what is true, what is dead, and
> how to resume. Governance lives in [`CONSTITUTION.md`](CONSTITUTION.md) (how to decide);
> read [`GRAVEYARD.md`](GRAVEYARD.md) before proposing any new direction.

- **Last updated:** 2026-06-24
- **Mission:** discover durable truth about whether *deletion is erasure* in agent /
  vector-database memory, and turn surviving truth into durable forensic assets.
- **Phase:** experiments **SATURATED**; in **implementation / hardening / packaging**.
- **Status of the kernel:** ALIVE — survived every executed attack to date.

---

## 1. The one surviving kernel

**Anti-forensic deletion residue in vector databases.**

Question under test: *After an official `delete()` returns success, the logical layer
reports clean, and plaintext/WAL residue is purged by compaction — does the embedding
vector persist on disk, and can it be reconstructed back to the original text?*

Answer, from executed experiments (CPU-only, single box, seeds fixed):

- **YES, the vector persists** — bit-identical, in ChromaDB's HNSW segment
  `data_level0.bin`, recoverable by a blind byte-parse with no schema/IDs.
- **YES, it inverts to text** — vec2text (gtr-base) reconstructs trigger-bearing text
  (cosine 0.89–0.97; specificity control passes: POISON token-overlap 4.0/5 vs
  BENIGN/RANDOM 0.0).
- **Deletion SELF-IDENTIFIES the residue** — the hnswlib `DELETE_MARK` bit selects
  exactly the deleted vectors (5 of 3005), so erasure makes the content *easier* to
  find, not harder. This is the novel step beyond Stahlberg SIGMOD'07 (plaintext
  deleted-record persistence).

### The sharp, defensible claim

A **post-delete recovery window is universal** across all 6 real engines tested. Its
**duration is unbounded ONLY on ChromaDB** — every other engine reclaims via a
maintenance pass (vacuum / optimizer / compaction-GC / tombstone-cleanup) that is
itself gated by thresholds or timers and often does not fire for realistic
right-to-be-forgotten (small-ratio) deletions.

| Engine | Residue right after delete | Reclamation trigger | Window |
|---|---|---|---|
| **ChromaDB** | yes (5/5, bit-identical, DELETE_MARK self-id) | **none observed** (4 attacks + 50k writes + drop + idle) | **unbounded** |
| Milvus (standalone 2.5.10) | yes | GC after a *completed* high-ratio compaction | ~360s |
| Weaviate (1.28.2) | yes | tombstone cleanup | ~cleanup interval (70s @ 5s; default 300s) |
| Qdrant (server, Rust) | yes | vacuum optimizer | when optimizer fires |
| pgvector (HNSW index) | yes | plain VACUUM | next (auto)vacuum |
| pgvector / Postgres (heap) | yes | VACUUM FULL only | until VACUUM FULL |
| FAISS / Qdrant-local (embedded) | **no** (reserialize/rewrite compacts) | — | clean (true negative) |

Full evidence + per-claim traceability: [`experiments/residue/FINDINGS.md`](experiments/residue/FINDINGS.md).

### Honest bounds (do not overclaim)

- Residue appears in HNSW only **after** the vector flushes WAL→HNSW at least once;
  delete-before-first-flush leaves no HNSW residue (lived in transient WAL plaintext).
- ChromaDB "never reclaims" = **no reclaim observed** under all tested pressures; the
  Rust compaction internals are not source-verified. Negative examples exist elsewhere
  (Qdrant/pgvector demonstrably purge), so durability is genuinely engine-specific.
- Inversion shown for gtr-base only (vec2text ships gtr + ada-002). Residue
  *existence/recovery* is embedding-model-independent (shown on gtr-768 and MiniLM-384).
- Quantization is a *partial* mitigation: trigger-preservation fp32 0.88 / fp16 0.88 /
  int8 0.80 (dominant formats stay invertible); PQ-m96 0.40; 1-bit 0.24.

---

## 2. Durable assets created (the point of the work)

Everything lives under [`experiments/residue/`](experiments/residue/).

- **`tool/vdbresidue.py`** — the headline asset. Read-only, deterministic, no-LLM
  DFIR / GDPR-erasure forensic auditor. Subcommands: `inspect`, `recover`, `report`,
  `acquire`, `match`, `verify`. Blind recovery for Chroma (dual signal: DELETE_MARK
  bit + sqlite seq-id orphan, 0 false positives) and Milvus (parquet delta tombstones);
  `match` mode does exact-byte presence for known vectors on *any* engine — streamed in
  bounded chunks (O(chunk) memory, runs on multi-GB stores) and searched per-file (no
  cross-file-boundary false positives). Chain-of-custody JSONL on every op. Exit code 2 =
  recoverable residue found (CI / erasure gate).
- **`tool/selftest.py`** — deterministic, ~5s, no downloads. Builds a tiny Chroma DB,
  deletes 7, asserts exact recovery. **PASS** (7/7, 0 false positives) as of 2026-06-23.
- **`scripts/vecdb_residue_audit.py`** — the original Chroma erasure auditor.
- **`scripts/phase1..18` + `cross_version/`** — the executed experiment tree. Each claim
  in FINDINGS.md traces to a script + a `results/*.json` + a `logs/*.log`.
- **`FINDINGS.md`** — every surviving claim with evidence pointers and self-corrections.
- **`FILE_LAYOUTS.md`** — reverse-engineered on-disk formats (chroma header.bin offsets +
  DELETE_MARK byte; milvus parquet+delta; pgvector TOAST prefix; qdrant/weaviate notes).
- **`MANIFEST.sha256` + `verify_manifest.sh`** — chain-of-custody over the residue tree.
- **`run_all.sh`** — tiered reproduction (cpu / postgres / docker / all / verify).
- **`REPRODUCE.md`, `requirements.lock.txt`, `results/ENV.txt`** — pinned, deterministic.
- **`disclosure/`** — coordinated-disclosure DRAFTS (chroma, milvus, weaviate,
  qdrant_pgvector_fyi). **NOT SENT — human approval gate.**

---

## 3. What is NOT done / blocked

- **Disclosure not sent.** Ethical + human decision; drafts ready in `disclosure/`.
- **Formal publication** deliberately deferred until evidence stabilizes (it has;
  the gate is now "is the paper worth more than the tool?" — see open question below).
- **Inversion on non-gtr models** untested (vec2text ships gtr + ada-002 only). Does
  NOT affect residue existence/recovery claims, which are model-independent.
- Earlier resource blocks (docker, PG18 dev headers) are RESOLVED — Qdrant-server,
  Weaviate, real Milvus standalone, and pgvector HNSW index were all tested after unblock.

---

## 4. Reproduce from scratch

```bash
cd experiments/residue
python3 -m venv .venv && .venv/bin/pip install -r requirements.lock.txt
.venv/bin/python tool/selftest.py          # deterministic, no downloads -> SELFTEST PASS
./verify_manifest.sh                        # chain-of-custody check
./run_all.sh cpu                            # CPU-only phases
./run_all.sh docker                         # engine phases needing docker
```

The `.venv/`, `hf_cache/`, `db/`, `build/` dirs are reproducible-from-scratch and are
git-ignored on purpose. `results/` and `logs/` ARE evidence and are committed.

---

## 4b. Layer-up: the Deletion-Durability Registry (Pillar #1 → benchmark layer)

Per the constitution's ladder (Tools → Benchmarks → Taxonomies → Registries), the saturated
per-engine evidence has been elevated from prose into a structured, evidence-traceable
artifact at [`benchmarks/deletion-durability/`](benchmarks/deletion-durability/):

- `registry.json` — one entry per engine; **every quantitative claim cites a committed
  `experiments/residue/results/*.json`**.
- `build_matrix.py` — validator + matrix generator; **fails the build if any cited evidence
  file is missing**, or if a high/medium-confidence row has no evidence (structural NO FAKE
  RESULTS gate; negative-tested). Renders `MATRIX.md`.
- Surfaces 2 honest evidence gaps as `unverified`/`low` (Postgres heap, pgvector HNSW index)
  — these are now tracked to-dos (re-run + commit structured results), not buried prose.

This is the engine-independent framing (escapes the "Chroma project" trap) and the seed of
the `benchmarks/ taxonomies/ registries/` platform layout.

## 4c. Up another layer: the VEDC standard (Registry → Standard)

[`standards/erasure-durability/`](standards/erasure-durability/) defines **VEDC** — a normative
classification of vector-store erasure durability (classes VEDC-U / AU / AT / M / N, `+S` for
self-identifying deletion). `classify.py` is the **executable** conformance tool: it reuses the
registry's evidence gate and generates `CLASSIFICATION.md`, so nothing unbacked can be
classified. It assigns a conformance level — **Confirmed** (multi-seed/cross-version) vs
**Provisional** (single trajectory). As of v0.1 only **ChromaDB (VEDC-U+S) is Confirmed**; the
other 7 are Provisional → multi-seed replication is the named next experiment. The spec is
Reviewer-#2-hardened: it disclaims novelty of the persistence phenomenon (Stahlberg SIGMOD'07,
secure-deletion lit, GDPR Art.17), states the exact delta, and includes an anti-gaming /
positive-control conformance rule and a dual-use ethics stance.

CI: [`.github/workflows/registry-integrity.yml`](.github/workflows/registry-integrity.yml)
re-runs both gates on every push/PR and fails if generated artifacts go stale → the
NO-FAKE-RESULTS gate is now permanent, not manual. Governance: [`DOCTRINE.md`](DOCTRINE.md)
(14 departments, Reality veto) operationalizes the board.

## 4d. Replication status (Provisional → Confirmed) + new engines

Multi-seed replication executed for every readily-confirmable engine (SPEC §5 needs ≥3
independent valid trials, positive control held). **10 engines, 7 Confirmed.**

NEW (LanceDB, 10th engine, VEDC-M+S Confirmed, phase25 ×3 seeds): a real versioned-columnar
vector DB. Soft-deletes via deletion files; residue persists after delete AND through a routine
`optimize` at low (right-to-erasure) delete ratios — only high-ratio compaction materializes +
purges. Same class as Postgres-heap (manual) but threshold-gated like Milvus small-ratio.

NEW (page-aware detector): `vdbresidue` gained a SQLite-page-aware match (overflow-page
de-interruption) — raw byte-search under-counts SQLite-backed stores because vectors split
across overflow pages (each prefixed with a 4-byte next-page pointer). With it, **sqlite-vec**
(9th engine) measures **VEDC-N Confirmed** (phase24, 3 seeds): 5/5 recoverable before delete
(raw saw 2/5), 0/5 after a committed delete — vec0 compacts its chunk; first production engine
with no recoverable post-delete residue. SPEC §9 limitation is now ADDRESSED; selftest covers it.

**Confirmed (6):**

- **ChromaDB** (VEDC-U+S) — phase2 ×5 seeds + cross-version.
- **Weaviate** (VEDC-AT) — phase19 ×3 seeds, purged 70s in every trial.
- **pgvector index** (VEDC-AU) — phase8 seeds 0/1/2, VACUUM purges in all.
- **Postgres heap** (VEDC-M+S) — phase4 seeds 0/1/2, survives plain VACUUM (4/5), VACUUM FULL purges.
- **Qdrant-server** (VEDC-AU) — phase22 4 valid of 5 (seed 1 discarded: positive-control failure per SPEC §4).
- **sqlite-vec** (VEDC-N) — phase24 ×3 seeds via the page-aware detector; no recoverable residue after delete.
- **LanceDB** (VEDC-M+S) — phase25 ×3 seeds; soft-delete residue purged only by high-ratio compaction.

**Still Provisional (by deliberate cost/value call, not gap):**
- **Milvus** (VEDC-AT+S) — DEFERRED. Already has the strongest Provisional evidence of any
  engine (3 conditions: phase11 small-ratio durable, phase12 high-ratio compaction-completed-
  still-present, phase15 purge-at-360s). Multi-seed needs a ~16-min, 3-container
  (etcd+MinIO+Milvus) run per the phase11/15 harness; marginal value (confirm 360s timing)
  judged below cost. Resumable: clone phase19/phase22 structure over a per-seed Milvus cluster.
- **FAISS, Qdrant-local** — negative controls; Confirmed status is not meaningful for a control
  (their no-false-positive role is already demonstrated by every positive engine's positive
  control). Left Provisional by design.

## 5. Open question for the next cycle (decide with the board, not with hope)

The kernel survived saturation. The honest fork:

1. **Tool-first authority** (preferred by current evidence): `vdbresidue` is a real,
   reusable DFIR/GDPR asset. Harden it, broaden engine coverage in `match` mode, ship it
   as the reference erasure-verification tool. Compounds. Survives without a paper.
2. **Paper** ("deletion is not erasure in vector DBs; deletion self-identifies the
   residue"): defensible and novel beyond SIGMOD'07, but must clear Reviewer #2 against
   MemAudit/MemLineage/secure-deletion literature (see GRAVEYARD). Paper is a *side
   effect*, never the goal.

Default per doctrine: **strengthen the tool (asset that compounds) before writing the
paper (output that decays).** Do not broaden scope into a "platform." Re-run the board
review in `GRAVEYARD.md` §"How directions die here" before committing effort.

---

## 6. The standing rule

Nature decides. Null hypothesis owns everything. No invented results, no narrative
rescue, no resurrecting the graveyard without genuinely new evidence. Convergence over
activity — an idle system with no remaining meaningful attack is healthy.
