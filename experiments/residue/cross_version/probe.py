#!/usr/bin/env python3
"""Cross-version residue probe for ChromaDB (model-free, deterministic).
Build collection with seeded explicit embeddings -> delete 5 -> compact -> verify logical
deletion -> bit-identical byte-search all persist files for the 5 deleted vectors -> try
DELETE_MARK parse. Robust to layout changes (byte search is alignment/format-independent).
Output one JSON line. Usage: probe.py <db_path>"""
import sys, os, glob, shutil, gc, json
import numpy as np
import chromadb
ver = getattr(chromadb, "__version__", "?")
DIM = 32; DB = sys.argv[1]
rng = np.random.default_rng(0)
secret = rng.standard_normal((5, DIM)).astype(np.float32)
filler = rng.standard_normal((300, DIM)).astype(np.float32)
shutil.rmtree(DB, ignore_errors=True)
res = {"version": ver}
try:
    cl = chromadb.PersistentClient(path=DB)
    col = cl.create_collection("verprobe", metadata={"hnsw:space": "l2"})
    col.add(ids=[f"s{i}" for i in range(5)], embeddings=secret.tolist())
    col.add(ids=[f"f{i}" for i in range(300)], embeddings=filler.tolist())
    col.delete(ids=[f"s{i}" for i in range(5)])
    for b in range(4):
        col.add(ids=[f"g{b}_{i}" for i in range(300)],
                embeddings=rng.standard_normal((300, DIM)).astype(np.float32).tolist())
        del col, cl; gc.collect()
        cl = chromadb.PersistentClient(path=DB); col = cl.get_collection("verprobe")
    res["logical_deleted_gone"] = col.get(ids=[f"s{i}" for i in range(5)])["ids"] == []
    res["count"] = col.count()
    del col, cl; gc.collect()
    files = [f for f in glob.glob(DB + "/**/*", recursive=True) if os.path.isfile(f)]
    raw = b"".join(open(f, "rb").read() for f in files)
    res["residue_present"] = sum(secret[k].tobytes() in raw for k in range(5))
    segs = glob.glob(DB + "/**/data_level0.bin", recursive=True)
    res["segfmt"] = "data_level0.bin" if segs else "none"
    res["delete_marked"] = None
    if segs:
        data = open(segs[0], "rb").read(); stride = 132 + DIM*4 + 8
        if len(data) % stride == 0:
            n = len(data)//stride
            res["delete_marked"] = sum(1 for i in range(n) if data[i*stride+2] & 0x01)
except Exception as e:
    res["error"] = repr(e)
finally:
    shutil.rmtree(DB, ignore_errors=True)
print("PROBE_JSON " + json.dumps(res))
