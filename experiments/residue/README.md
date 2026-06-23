# Vector-database deletion residue — research artifact

Empirical study of whether "deleted" embedding vectors remain physically recoverable (and
text-reconstructable) on disk across production vector databases, plus a read-only forensic
tool. Everything here is reproducible, manifest-verified, and CPU-only.

> Scope note: this is a **data-lifecycle / "deletion ≠ secure erasure"** study (same family as
> Stahlberg et al., SIGMOD 2007), not a memory-safety/RCE finding. It requires filesystem/
> backup/snapshot access to the persistence directory. No "first"/novelty claims are made;
> see the honest novelty notes in `disclosure/README.md`.

## Headline (evidence-backed, with self-corrections)
1. **Universal post-delete recovery window** — in all 6 real engines tested (ChromaDB, Milvus,
   Qdrant-server, pgvector, Postgres-heap, Weaviate) the deleted vector is **bit-identical
   recoverable** from disk after the delete API returns and the logical layer reads clean.
2. **ChromaDB is the UNIQUE never-purges engine** — residue survives 50k writes, restarts,
   collection-drop, four targeted reclaim attacks (`phase13`), and 360s idle (`phase16`). The
   others reclaim on a timer/threshold: Weaviate ~70s (`phase14`), Milvus ~360s (`phase15`),
   Qdrant (optimizer, `phase9`), pgvector (VACUUM, `phase8`).
3. **Self-identifying deletion** — Chroma's hnswlib `DELETE_MARK` and Milvus's delta tombstone
   let a blind reader recover *exactly* the erased records (`phase6`).
4. **Invertible to text** — recovered vectors invert (vec2text/gtr-base) to trigger-bearing
   text for dominant storage precisions (fp32/fp16/int8); degraded under PQ, defeated by 1-bit
   (`phase5`; statistical hardening with CIs in `phase18`).
5. **Behavior is architectural in Chroma** — identical across 0.5.23 → 1.5.9 incl. the 1.0
   Rust-core rewrite (`cross_version/`).

See `FINDINGS.md` for the full evidence chain and `FILE_LAYOUTS.md` for reverse-engineered
on-disk formats. Per-engine purge timings are in the Final taxonomy table in `FINDINGS.md`.

## Layout
```
FINDINGS.md            full results + every self-correction (the scientific record)
FILE_LAYOUTS.md        reverse-engineered on-disk vector storage formats
REPRODUCE.md           how to re-run each phase
MANIFEST.sha256        chain-of-custody hashes of all artifacts (verify_manifest.sh)
run_all.sh             tiered one-command reproduction (cpu|postgres|docker|all|verify)
requirements.lock.txt  pinned deps (CPU-only)
scripts/               phase1..phase18 experiments (+ legacy)
results/               *.json results, ENV.txt, poison_embeddings.npy
logs/                  raw run logs
tool/                  vdbresidue — read-only forensic auditor + selftest + README
disclosure/            DRAFT vendor disclosures (NOT SENT — human-gated)
cross_version/         ChromaDB version bisection harness
db/, .venv/, hf_cache/, build/   gitignored (reproducible from scratch)
```

## Reproduce
```
bash run_all.sh verify     # check artifact manifest (tamper/chain-of-custody)
bash run_all.sh cpu        # phases needing only python (chroma/faiss/qdrant-local/milvus-lite)
bash run_all.sh postgres   # + pgvector/postgres (needs PG18 + built pgvector)
bash run_all.sh docker     # + qdrant/weaviate/milvus servers (needs `sudo docker`)
python tool/selftest.py    # ~5s deterministic tool self-test (no downloads) -> PASS
```

## Tool: vdbresidue ("read-only forensics for vector DBs")
`tool/vdbresidue.py` — deterministic, read-only, no-LLM, chain-of-custody auditor.
`inspect | recover | report | acquire | match | verify`. Blind deleted-vector recovery for
Chroma (dual signal: DELETE_MARK ∪→precedence sqlite-orphan, 0 false positives) and Milvus
(parquet+delta); exact-byte `match` for any engine. See `tool/README.md`.

## Scientific integrity record (self-corrections — the asset is *surviving* truths)
- HNSW residue is flush-gated (early "no residue" was pre-flush).
- "Durable across append-only engines" was too strong → only ChromaDB never purges; Milvus/
  Weaviate/Qdrant/pgvector all reclaim (timed/threshold).
- "High delete ratio purges" → refuted for Chroma (ratio-independent); confirmed bounded elsewhere.
- Weaviate/Milvus "durable" → corrected: they purge (~70s / ~360s) on a longer timeline.
- Tool DELETE_MARK-only detection had a false-negative blind spot (low-write state) → fixed
  with a verified sqlite-orphan fallback (`phase17`), avoiding the false positives a naive
  union would introduce.

## Status
Evidence saturated for the headline. Disclosures drafted, **not sent** (awaiting approval).
Open: inversion for non-gtr models (no pretrained inverter); cross-version bisection of the
non-Chroma engines (lower value).
