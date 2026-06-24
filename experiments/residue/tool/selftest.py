#!/usr/bin/env python3
"""Deterministic self-test for vdbresidue — no model, no network, no LLM.
Builds a tiny Chroma DB with seeded explicit embeddings, deletes a known subset,
compacts, then asserts the tool recovers exactly those vectors, bit-identically.
Run: python tool/selftest.py   (exit 0 = PASS)
"""
import os, sys, shutil, gc, glob
import numpy as np
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.abspath(os.path.join(HERE,".."))
sys.path.insert(0, HERE)
os.environ.setdefault("HF_HOME", os.path.join(ROOT,"hf_cache"))
import chromadb
import vdbresidue as V

DIM=64; NDEL=7; DB=os.path.join(ROOT,"db","_selftest_chroma")
rng=np.random.default_rng(12345)
secret=rng.standard_normal((NDEL,DIM)).astype(np.float32)
filler=rng.standard_normal((400,DIM)).astype(np.float32)
if os.path.exists(DB): shutil.rmtree(DB)
cl=chromadb.PersistentClient(path=DB); col=cl.create_collection("selftest", metadata={"hnsw:space":"l2"})
col.add(ids=[f"s{i}" for i in range(NDEL)], embeddings=secret.tolist())
col.add(ids=[f"f{i}" for i in range(400)], embeddings=filler.tolist())
col.delete(ids=[f"s{i}" for i in range(NDEL)])
for b in range(3):  # compact (WAL->HNSW flush)
    col.add(ids=[f"g{b}_{i}" for i in range(400)], embeddings=rng.standard_normal((400,DIM)).astype(np.float32).tolist())
    del col, cl; gc.collect(); cl=chromadb.PersistentClient(path=DB); col=cl.get_collection("selftest")
assert col.count() and col.get(ids=[f"s{i}" for i in range(NDEL)])["ids"]==[], "logical layer not clean"
del col, cl; gc.collect()

backend=V.detect_backend(DB)
infos, vecs, labels = V.recover_dispatch(DB, backend)
ok_backend = backend=="chroma"
ok_count = len(labels)==NDEL
# fidelity: every deleted secret must be bit-identical among recovered
rec=vecs if len(vecs) else np.zeros((0,DIM),np.float32)
matched=sum(any(np.array_equal(rec[j], secret[k]) for j in range(len(rec))) for k in range(NDEL))
ok_fidelity = matched==NDEL
# match mode: deleted secrets must be found present; a random vector must be absent (no FP)
mres, _, _ = V.match_targets(DB, secret)
rnd = np.random.default_rng(999).standard_normal((3,DIM)).astype(np.float32)
mrnd, _, _ = V.match_targets(DB, rnd)
ok_match = all(r["present"] for r in mres) and not any(r["present"] for r in mrnd)
# streaming boundary: a tiny chunk forces vectors to straddle read boundaries; the overlap
# carry in _stream_search must still find every one (regression guard for chunked matching).
seg = next(iter(glob.glob(os.path.join(DB, "**", "data_level0.bin"), recursive=True)), None)
ok_stream = True
if seg is not None:
    sniff = [(k, secret[k].astype(np.float32).tobytes()) for k in range(NDEL)]
    ok_stream = V._stream_search(seg, sniff, chunk=37) == set(range(NDEL))
shutil.rmtree(DB, ignore_errors=True)

# ---- milvus backend regression: second engine, otherwise-untested recover path ----
# Build a minimal segment(data)+tombstone(delta) parquet layout, delete a known id subset
# via the delta log, and assert milvus_recover returns exactly those rows bit-identically.
ok_milvus = True; milvus_status = "milvus=skip(no-pyarrow)"
try:
    import pyarrow as pa, pyarrow.parquet as pq
    MDB = os.path.join(ROOT, "db", "_selftest_milvus")
    if os.path.exists(MDB): shutil.rmtree(MDB)
    mseg = os.path.join(MDB, "seg", "data"); os.makedirs(mseg)
    mdelta = os.path.join(MDB, "seg", "delta"); os.makedirs(mdelta)
    NROW = 20; mdel = [3, 7, 11, 15]
    mvecs = np.random.default_rng(2024).standard_normal((NROW, DIM)).astype(np.float32)
    pq.write_table(pa.table({"id": pa.array(list(range(NROW)), pa.int64()),
                             "vec": pa.array([v.tolist() for v in mvecs], pa.list_(pa.float32()))}),
                   os.path.join(mseg, "0.parquet"))
    pq.write_table(pa.table({"id": pa.array(mdel, pa.int64())}), os.path.join(mdelta, "0.parquet"))
    _mi, mv, ml = V.milvus_recover(MDB)
    got = sorted(l["id"] for l in ml)
    mfid = all(any(np.array_equal(mv[j], mvecs[k]) for j in range(len(mv))) for k in mdel)
    ok_milvus = (V.detect_backend(MDB) == "milvus") and got == sorted(mdel) and mfid
    shutil.rmtree(MDB, ignore_errors=True)
    milvus_status = f"milvus={'ok' if ok_milvus else 'FAIL'}({len(ml)}/{len(mdel)})"
except ImportError:
    pass

print(f"backend={backend} expected_deleted={NDEL} recovered={len(labels)} bit_identical_matched={matched} "
      f"match_present={sum(r['present'] for r in mres)}/{NDEL} match_false_positives={sum(r['present'] for r in mrnd)} "
      f"stream_boundary={'ok' if ok_stream else 'FAIL'} {milvus_status}")
if ok_backend and ok_count and ok_fidelity and ok_match and ok_stream and ok_milvus:
    print("SELFTEST PASS"); sys.exit(0)
print("SELFTEST FAIL"); sys.exit(1)
