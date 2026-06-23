# Vector-DB deletion residue — reproduction runbook

All artifacts are self-contained under this directory (`experiments/residue/`).
No network is needed at run time (models cached in `hf_cache/`); only the first
ever run downloaded weights.

## Environment
- See `results/ENV.txt` (Python 3.13, Linux x86_64, Postgres 17.5, 12 cores, CPU-only).
- Exact package versions: `requirements.lock.txt` (key: chromadb 1.5.9, torch 2.12.1+cpu,
  transformers 4.46.3, vec2text 0.0.13, faiss-cpu 1.14.3, qdrant-client 1.18.0,
  pymilvus 3.0.0 / milvus-lite 3.0, numpy 2.4.6, pyarrow 24.0.0).
- Interpreter: `./.venv/bin/python` (call the binary directly; the venv was relocated
  so `pip`'s shebang is stale — use `./.venv/bin/python -m pip`).

## Hypothesis under test
After an official `delete` AND routine maintenance (compaction / VACUUM), does the
embedding vector persist on disk and still invert (vec2text) to the original text?

## Phases (each writes results/<phase>*.json and logs/<phase>*.log)
```
# 0. inverter sanity (clean embeddings)            ~3 min
./.venv/bin/python scripts/00_gate0_invert.py        # legacy copy; gate passed

# 1. Chroma residue -> invert -> specificity        ~12 min/seed
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ./.venv/bin/python scripts/phase1_chroma_residue_inversion.py 0

# 2. Chroma durability (50k writes, restarts, drop)  ~2 min/seed ; run seeds 0..4
for s in 0 1 2 3 4; do ./.venv/bin/python scripts/phase2_persistence_destruction.py $s; done

# 3. cross-backend (FAISS, Qdrant-local)             ~1 min
./.venv/bin/python scripts/phase3_cross_backend.py
#    Milvus + structured parquet recovery: inline diagnostics (see logs / memory note)

# 4. Postgres heap + VACUUM (userspace PG17 cluster) ~1 min
./.venv/bin/python scripts/phase4_postgres_heap.py

# 5. quantization robustness of inversion            ~21 min
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ./.venv/bin/python scripts/phase5_quantization_inversion.py
```

## Recovery primitives (the "blind attacker" parse)
- Chroma HNSW segment `*/data_level0.bin`: hnswlib layout M=16 -> per-element stride
  `OFF=132, STRIDE=132+DIM*4+8`; vector floats at `OFF`. Also assumption-free byte-search
  for the exact float32 pattern.
- Milvus: read `collections/*/partitions/*/data/*.parquet` (column `vector`); the
  `delta/*.parquet` is only a soft-delete tombstone (`id`,`_seq`).
- Postgres: vector bytea is TOASTed; scan main heap + TOAST relation files
  (`pg_relation_filepath(reltoastrelid)`), match a <=1900B prefix (TOAST chunk size).

## Notes / scope
- Inversion uses the pretrained vec2text `gtr-base` corrector; residue *existence* is
  embedding-model-independent, *inversion* is model-specific (gtr-base / ada-002 ship
  pretrained inverters).
- Resource-blocked here (need sudo/docker): Qdrant server, Weaviate, real Milvus
  cluster, and pgvector's HNSW index (server dev headers absent — only Postgres heap
  channel tested).
