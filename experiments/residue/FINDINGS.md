# Vector-DB deletion residue — findings (autonomous wet-lab run)

Every claim below traces to a script in `scripts/`, a JSON in `results/`, and a log in
`logs/`. Environment: `results/ENV.txt`, `requirements.lock.txt`. CPU-only, single box.

## Question
After an official `delete` returns success and the logical layer (and WAL plaintext)
is clean, does the embedding vector persist on disk, and can it be reconstructed to the
original text?

## Surviving claims (with evidence)

1. **Residue exists, bit-identical** (Chroma 1.5.9, gtr-base, `phase1`, `results/phase1_seed0.json`).
   After delete + compaction: logical count 0, WAL plaintext hits 0, but 5/5 deleted
   vectors are byte-for-byte present in `data_level0.bin`; a blind stride-parse recovers
   them at cosine 1.0.

2. **Residue inverts to text** (`phase1`, vec2text gtr-base corrector).
   Recovered vectors invert to trigger-bearing text: cosine 0.89–0.97, trigger-token
   preservation 0.8–1.0. Specificity control: poison-token overlap POISON 4.0/5 vs
   BENIGN 0.0 vs RANDOM 0.0 — the inverter is reading the residue, not hallucinating.

3. **Durable** (`phase2`, seeds 0–4, `results/phase2_seed*.json`).
   Residue present 5/5 at every checkpoint after 1k/5k/20k/50k inserts, 3 restart
   cycles, AND after `delete_collection` — reproducible across all 5 seeds. (Nuance:
   absent at 0 writes — the vector must flush WAL→HNSW once before it persists there.)

4. **A post-delete recovery WINDOW exists in EVERY real engine tested; persistence
   duration varies sharply** (positive-control-validated). SELF-CORRECTION: my earlier
   "durable across append-only-segment engines" was too strong. Refined taxonomy:
   - **Unbounded (never auto-purges) — Chroma only**: residue survives 50k writes,
     restarts, collection-drop. The durable, novel kernel.
   - **Bounded by built-in maintenance** (residue present right after delete, then purged):
     real **Qdrant server** (Rust, `phase9`): 5/5 present after delete → 0/5 after the
     vacuum optimizer triggers. **pgvector HNSW index** (`phase8`): present after delete →
     purged by plain VACUUM. **Postgres heap** (`phase4`): survives plain VACUUM (4/5),
     purged by VACUUM FULL. **Milvus** (`phase3b`): present after delete+flush+compact
     (milvus-lite compact was a no-op; real segment-merge compaction untested — likely purges).
   - **Clean (no recoverable residue)**: FAISS (reserialize), Qdrant-local toy (rewrite-on-close).
   Operational takeaway: an attacker/forensic reader with file access between a delete and
   the next compaction/vacuum recovers the bit-identical vector in ALL real engines; for
   Chroma, at any time indefinitely.

   Original (now-superseded) framing kept for the record — "3 production architectures":
   - Chroma (hnswlib append-only HNSW segment): durable, above.
   - Milvus (milvus-lite, real parquet segment + delta tombstone): after delete+flush+
     compact the segment retains all 5 vectors bit-identical; structured recovery from
     the parquet at cosine 1.0; the delete only appended a 5-row tombstone.
   - Postgres heap (userspace PG, vectors as bytea TOAST, `phase4`): deleted vector
     survives delete AND plain VACUUM (4/5); only VACUUM FULL (table rewrite) purges.
   - pgvector HNSW INDEX (PG18 + built pgvector 0.8.3, `phase8`, positive-control-validated):
     vector present in index pages after delete (cos 1.0), but **plain VACUUM PURGES it**
     (cos -> 0.13); VACUUM FULL/REINDEX likewise. REFINEMENT (self-correction): pgvector's
     index channel SELF-CLEANS under routine autovacuum, unlike Chroma (never purges). Only
     pgvector's heap channel lingers (until VACUUM FULL). pgvector is the least leaky engine.
   - Counter-examples (clean): FAISS flat remove_ids+write_index (reserialize compacts),
     Qdrant-local (embedded engine rewrites store on close). Both fail positive control
     for residue → genuine negatives. NOT the Rust Qdrant server.

5. **Selective recovery — deletion TAGS the residue** (`phase6`, `results/phase6_blind_deletemark.json`).
   Reading only raw `data_level0.bin`, the persisted hnswlib `DELETE_MARK` bit selects
   exactly the 5 deleted vectors out of 3005 (all poison covered, cosine 1.0). Cross-engine
   analog: Milvus delta lists deleted ids; Postgres dead tuples carry xmax. Deletion makes
   the erased content *easier* to find, not harder — beyond SIGMOD'07 "records persist".

6. **Replicates on a 2nd embedding model with real data** (`phase7`, MiniLM-L6-v2 dim 384).
   Fresh independent DB, real embeddings, realistic PII secrets, no crafted poison, no
   gaussian filler: 8 deleted "right-to-be-forgotten" records all recoverable after
   compaction. Rebuts synthetic-data-bias for the residue + selective-recovery claims.

## Bounds / mitigations (honest scope)

- **Quantization** (`phase5`, `results/phase5_quantization.json`, mean trigger-preservation
  of inverted residue): fp32 0.88, fp16 0.88, int8-scalar 0.80 → the dominant storage
  formats keep the residue invertible. PQ-m96 0.40 (codebook undertrained → lower bound),
  1-bit binary 0.24 → aggressive lossy compression is a *partial* mitigation only.
- **Inversion** demonstrated for gtr-base (vec2text ships pretrained gtr + ada-002 only);
  residue *existence/recovery* is embedding-model-independent (shown on gtr-768 and MiniLM-384).

## Now tested after unblock (passwordless sudo + PG18 dev headers installed)
- **pgvector HNSW index** built (0.8.3 vs PG18) and tested — `phase8` (see claim 4).
- **Real Qdrant server** (docker) tested — `phase9` (see claim 4).

## Now tested (this section's earlier "not tested" items are resolved — see Final taxonomy)
- Weaviate (`phase10`, `phase14`): tombstone cleanup purges (~70s @ interval=5s).
- Real Milvus standalone (`phase11`, `phase12`, `phase15`): GC purges ~360s after a completed
  high-ratio compaction.
- Still open: inversion for non-gtr embedding models (vec2text ships gtr + ada-002 only) — the
  residue *existence/recovery* is model-independent regardless.

## Artifact
`scripts/vecdb_residue_audit.py` — deletion-effectiveness auditor for Chroma. Point it at
a persist dir; it reports logically-deleted-but-physically-recoverable vectors (auto-detects
dim from `header.bin`), exit 2 if any found. Validated: 8/8 and 5/5 true positives, 0 false
positives on a no-deletion DB. Defensive use: verify erasure/GDPR deletions actually removed data.

## Self-falsification: hunting a hidden reclaim path in ChromaDB (`phase13`, `results/phase13_chroma_reclaim_attack.json`)
White-box (audit of installed chromadb 1.5.9): the default API is the Rust bindings
(`chromadb_rust_bindings.abi3.so`, a compiled "Local Compaction manager" — NOT source-readable).
The readable legacy Python HNSW path never reclaims (`replace_deleted`/`allow_replace_deleted`
off; `mark_deleted` only; labels strictly monotonic; `persist_dirty` appends, never rebuilds).
Black-box attack on the REAL Rust path — four attempts to force physical reclaim:
- A slot-reuse (add1000/del1000/add1000): victims 1000/1000 present, total_elems 2005 (fresh got
  NEW slots — no reuse), canary 5/5.
- B 100% delete + refill ×3: gen0 1000/1000 present, total 4000 (append-only), delete_marked 3000.
- C re-add SAME deleted ids with new vectors: OLD vectors 5/5 AND new 5/5 present (slot not reused).
- D tiny-batch churn (4000 adds across many sync_threshold=1000 crossings): 5/5 present.
VERDICT: **no reclaim observed** under any attack. Strengthens "unbounded". HONEST CAVEAT: the
Rust compaction internals are not source-verified; "no reclaim observed across all tested
pressures" — not a proof of "never". Negative examples DO exist in other engines (Qdrant
optimizer, pgvector VACUUM purge — see above), so the durability is genuinely engine-specific.

## Cross-version bisection — ChromaDB (`results/cross_version_chroma*.{jsonl,json}`)
Classification: **ARCHITECTURAL, not fixed in any release.** Tested on Python 3.13, model-free
probe (delete 5 → compact → bit-identical byte-search + DELETE_MARK parse):
- 0.5.23, 0.6.3, **1.0.21 (Rust-core rewrite)**, 1.3.7, **1.5.9 (latest)** — ALL leak identically
  (residue 5/5, delete_marked 5, logical layer clean).
- 0.4.24, 0.5.0 — not testable here (pre-1.0 dependency stack fails to import on Python 3.13);
  they use the same bundled hnswlib segment, so almost certainly identical.
The behavior survived the major 1.0 Rust-core rewrite and persists in the latest version →
inherent to the hnswlib HNSW segment format (mark-deleted + no reclamation), not a
version-specific regression.

## Symmetric idle test — ChromaDB (`phase16`, `results/phase16_chroma_idle.json`)
Weaviate/Milvus purge on an idle timer; does Chroma? Delete 5, flush to disk (5/5 present),
then keep a PersistentClient OPEN and IDLE, scanning at 0/30/60/120/240/360s + a fresh reopen.
Result: **5/5 present at every timepoint, segment bytes constant (537340), no purge** — Chroma
reclaims under neither writes (phase2/13) nor idle time (phase16). Confirms uniquely-unbounded.
NOTE (tool-relevant): in this low-post-delete-write state `delete_marked=0` in the segment —
the hnswlib DELETE_MARK is only written after enough writes trigger a compaction re-persist;
the deleted vector is physically present but UNMARKED (the delete lives in chroma.sqlite3).
=> DELETE_MARK-only detection false-negatives here; robust detection must also use
"segment label ∉ live sqlite ids" (fixed in `tool/vdbresidue.py`, see `phase17`).

## Final taxonomy (after phase13/14/15 self-corrections)

| Engine | Residue right after delete | Reclamation | Window |
|---|---|---|---|
| **ChromaDB** | yes (5/5, bit-identical, DELETE_MARK self-id) | **none observed** (4 attacks + 50k writes + drop) | **unbounded** |
| Milvus | yes | GC after completed compaction | ~360s (phase15) |
| Weaviate | yes | tombstone cleanup | ~cleanup interval (70s@5s; default 300s) |
| Qdrant (server) | yes | vacuum optimizer | when optimizer fires |
| pgvector (index) | yes | plain VACUUM | next (auto)vacuum |
| pgvector/Postgres (heap) | yes | VACUUM FULL only | until VACUUM FULL |

Headline: a post-delete recovery window is **universal**; it is **unbounded only on ChromaDB**.
The deletion is **self-identifying** on Chroma (DELETE_MARK) and Milvus (delta tombstone),
enabling targeted blind recovery of exactly the erased records during the window.

## Conclusion / status (after testing 5 real engines + 2 library/embedded)

The hypothesis did NOT die; it was sharpened by hostile evidence (two self-corrections).
Surviving, defensible claims:

1. **Universal post-delete recovery window** — in all 6 real engines tested (Chroma, Milvus,
   Qdrant-server, pgvector, Postgres-heap, Weaviate) the deleted vector is bit-identical
   recoverable from disk after the official delete API returns and the logical layer is
   clean (5/5 every time), until the engine's next compaction/vacuum/tombstone-cleanup.
   Purge is gated by a maintenance op (vacuum/optimizer/compaction/cleanup) that is itself
   gated by thresholds/schedules — and often does NOT fire for realistic deletions:
   - Chroma: no auto-purge at all → unbounded (5 seeds).
   - Milvus standalone v2.5.10 (`phase11`, real etcd+MinIO+Milvus): 5/5 persist through
     delete+flush+compact+GC at a 0.16% delete ratio — compaction threshold not met, GC
     doesn't touch the live segment. Durable for realistic small-ratio deletions.
   - Weaviate: SELF-CORRECTED. `phase10` (default cleanup interval 300s, 20s window) saw
     persistence — but `phase14` with `cleanupIntervalSeconds=5` shows the tombstone cleanup
     **PURGES the deleted vectors at ~70s** (5/5 at t≤40s → 0/5 at t=70s, stable to 160s;
     filler control retained). Weaviate AUTO-PURGES on a timer (default 300s); it belongs with
     Qdrant/pgvector, NOT with Chroma. The phase10 result was a too-short observation window.
   - Qdrant-server (`phase9`): purged once I forced an aggressive vacuum optimizer + churn.
   - pgvector index (`phase8`): purged by explicit plain VACUUM. Postgres heap (`phase4`):
     needs VACUUM FULL.
   KEY SYNTHESIS (updated after phase13/phase14): every engine retains the bit-identical vector
   after delete; physical purge requires a maintenance pass. The engines SPLIT cleanly:
   - **Auto-purges on a timer/threshold** (residue is transient): Weaviate (tombstone cleanup,
     ~interval, default 300s — `phase14` purged at 70s with interval=5s), Qdrant (vacuum
     optimizer), pgvector index (VACUUM). Postgres heap needs VACUUM FULL.
   - **No reclamation mechanism observed at all** (residue durable/unbounded): **ChromaDB ONLY** —
     survives 50k writes, restarts, collection-drop, AND four targeted reclaim attacks
     (`phase13`: slot-reuse, 100%-delete, id-reuse, churn). No code path or condition reclaimed.
   FINAL SELF-CORRECTION (`phase15`): Milvus DOES eventually purge — after a completed high-ratio
   compaction, GC reclaimed the superseded segment between 240–360s (poison 5/5→0/5, object store
   47MB→11MB). Caveat: the byte-scan positive control also stopped matching at t=360s (compaction
   re-encodes the surviving segment), so "purge" there is evidenced by the 4× store shrinkage +
   poison absence, with the live/deleted split resting on the logical layer rather than the byte
   scan at that point. Net: **ChromaDB is the UNIQUE engine among the six with no observed
   reclamation**; Milvus (~360s), Weaviate (~70s @ interval=5s; default 300s), Qdrant (optimizer),
   and pgvector (VACUUM) all reclaim. The right-to-be-forgotten exposure window is therefore
   unbounded only on Chroma; elsewhere it is bounded by the engine's maintenance interval.

## High delete-ratio purge confirmations (`phase12`)
Hypothesis: a high delete ratio triggers compaction and purges. Result: PARTIALLY REFUTED.
- **Chroma** 60% delete (600/1005) + 2000 writes: 600/600 deleted elements still on disk,
  poison 5/5 bit-identical. Ratio-INDEPENDENT — hnswlib never reclaims. (Confirms unbounded.)
- **Milvus** 40% delete (1200/3005): compaction state reached "Completed", yet poison 5/5
  STILL recoverable in MinIO after an 80s GC wait (aggressive GC config). The store grew
  monotonically 18→47 MB — compaction wrote NEW segments but GC did not collect the old
  ones (with the deleted vectors) in-window. SELF-CORRECTION: high ratio triggered
  compaction but did NOT yield observable purge; durable in the tested window. (Cannot
  claim Milvus never GCs — only that aggressive-config GC didn't fire within 80s of a
  completed compaction.)
Net: the only engines that demonstrably purged were Qdrant-server and pgvector, and only
when their maintenance (optimizer / explicit VACUUM) was forced. Chroma and Milvus stayed
durable even under high-ratio + completed compaction.
2. **ChromaDB: unbounded persistence + selective recovery** — the window never closes
   (50k writes / restarts / collection-drop), and the persisted hnswlib DELETE_MARK lets a
   blind reader pull exactly the deleted records. This is the novel kernel, beyond SIGMOD'07.
3. **Invertibility** — recovered vectors invert (vec2text/gtr-base) to trigger-bearing text
   for the dominant storage precisions (fp32/fp16/int8), degraded under PQ, defeated by 1-bit.
4. **Tool** — `vecdb_residue_audit.py` detects recoverable deleted vectors in a Chroma dir
   (validated 8/8 + 5/5 true positives, 0 false positives).

Bounded-vs-unbounded is the key axis: Qdrant-server + pgvector self-clean via built-in
vacuum/optimizer; Postgres-heap needs VACUUM FULL; Chroma never cleans.

Remaining (lower marginal value, expected "bounded like Qdrant"): Weaviate (LSM tombstones),
real Milvus standalone segment-merge compaction. Both runnable now that docker works.
