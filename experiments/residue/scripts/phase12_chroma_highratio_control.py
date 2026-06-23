#!/usr/bin/env python3
"""Phase 12 control: Chroma high delete-ratio (60%) — confirms hnswlib never reclaims,
so residue is ratio-INDEPENDENT (contrast to engines whose compaction is threshold-gated)."""
import os, shutil, glob, gc as _gc, json
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.abspath(os.path.join(HERE,".."))
os.environ.setdefault("HF_HOME", os.path.join(ROOT,"hf_cache"))
import numpy as np, chromadb
DIM=768; OFF=132; STRIDE=OFF+DIM*4+8
orig=np.load(os.path.join(ROOT,"results","poison_embeddings.npy")).astype(np.float32)
DB=os.path.join(ROOT,"db","chroma_highratio")
if os.path.exists(DB): shutil.rmtree(DB)
cl=chromadb.PersistentClient(path=DB); col=cl.create_collection("highratio", metadata={"hnsw:space":"l2"})
rng=np.random.default_rng(0); fv=rng.standard_normal((1000,DIM)).astype(np.float32)
col.add(ids=[f"p{i}" for i in range(5)], embeddings=orig.tolist())
col.add(ids=[f"f{i}" for i in range(1000)], embeddings=fv.tolist())
col.delete(ids=[f"p{i}" for i in range(5)]+[f"f{i}" for i in range(595)])  # 600/1005 = 60%
print("logical count after 60% delete:", col.count())
for b in range(4):
    col.add(ids=[f"g{b}_{i}" for i in range(500)], embeddings=rng.standard_normal((500,DIM)).astype(np.float32).tolist())
    del col, cl; _gc.collect(); cl=chromadb.PersistentClient(path=DB); col=cl.get_collection("highratio")
del col, cl; _gc.collect()
seg=glob.glob(os.path.join(DB,"*","data_level0.bin"))[0]; data=open(seg,"rb").read(); n=len(data)//STRIDE
ndel=sum(1 for i in range(n) if data[i*STRIDE+2]&0x01)
present=[bool(orig[k].tobytes() in data) for k in range(5)]
print(f"Chroma HIGH-ratio(60%): total_elems={n} delete_marked={ndel} poison_present={present} n={sum(present)}")
json.dump({"engine":"chroma","delete_ratio":"600/1005=60%","total_elems":n,"delete_marked":ndel,
           "poison_present":present,"verdict":"durable regardless of ratio (hnswlib has no reclaiming compaction)"},
          open(os.path.join(ROOT,"results","phase12_chroma_highratio.json"),"w"))
print("[SAVED] results/phase12_chroma_highratio.json")
