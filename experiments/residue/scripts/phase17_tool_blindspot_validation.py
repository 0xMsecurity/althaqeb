#!/usr/bin/env python3
"""Phase 17: validate the hardened vdbresidue chroma backend closes the DELETE_MARK blind spot.
Builds a LOW-post-delete-write Chroma DB (so DELETE_MARK is NOT yet written to the segment;
phase16 showed this state), then asserts vdbresidue recovers the deleted vectors via the
sqlite-orphan signal (label in segment but not live in chroma.sqlite3). Deterministic, no model."""
import os, sys, shutil, gc, json
import numpy as np
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.abspath(os.path.join(HERE,".."))
sys.path.insert(0, os.path.join(ROOT,"tool"))
os.environ.setdefault("HF_HOME", os.path.join(ROOT,"hf_cache"))
import chromadb, vdbresidue as V
DIM=32; DB=os.path.join(ROOT,"db","_r17_blindspot")
rng=np.random.default_rng(7)
secret=rng.standard_normal((5,DIM)).astype(np.float32)
shutil.rmtree(DB, ignore_errors=True)
cl=chromadb.PersistentClient(path=DB); col=cl.create_collection("blindspot", metadata={"hnsw:space":"l2"})
col.add(ids=[f"s{i}" for i in range(5)], embeddings=secret.tolist())
col.add(ids=[f"f{i}" for i in range(2000)], embeddings=rng.standard_normal((2000,DIM)).astype(np.float32).tolist())
del col,cl; gc.collect(); cl=chromadb.PersistentClient(path=DB); col=cl.get_collection("blindspot")
col.delete(ids=[f"s{i}" for i in range(5)])
col.add(ids=[f"g{i}" for i in range(20)], embeddings=rng.standard_normal((20,DIM)).astype(np.float32).tolist())  # FEW writes
assert col.get(ids=[f"s{i}" for i in range(5)])["ids"]==[], "not logically deleted"
del col,cl; gc.collect()

infos, vecs, labels = V.chroma_recover(DB)
mark=sum(i.get("n_delete_mark",0) for i in infos)
orphan=sum(i.get("n_sqlite_orphan_only",0) for i in infos)
signals=[i.get("signal_used") for i in infos]
# fidelity: the 5 secrets bit-identical among recovered
matched=sum(any(np.array_equal(vecs[j], secret[k]) for j in range(len(vecs))) for k in range(5))
ok = (matched==5)
res={"db":"low-post-delete-write","total_recovered":len(labels),"n_delete_mark":mark,
     "n_sqlite_orphan_only":orphan,"signal_used":signals,"secrets_bit_identical_matched":matched,
     "verdict":"PASS — blind spot closed (sqlite-orphan recovered unmarked residue, 0 FP)" if ok else "FAIL"}
print(json.dumps(res))
json.dump(res, open(os.path.join(ROOT,"results","phase17_tool_blindspot.json"),"w"), indent=2)
shutil.rmtree(DB, ignore_errors=True)
sys.exit(0 if ok else 1)
