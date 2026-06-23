#!/usr/bin/env python3
"""
Phase 16 (symmetric self-falsification): Weaviate purges on a timer (~70s), Milvus GC ~360s.
Does ChromaDB's background Rust "Local Compaction manager" ALSO purge if simply given IDLE
time (no writes)? phase13 attacked with churn; this attacks with TIME. If Chroma purges on
idle, the "uniquely unbounded" headline collapses (that would be the most important result).

Setup: add 5 poison + filler, delete poison, flush to disk (confirm 5/5 on disk). Then keep a
PersistentClient OPEN and idle, scanning data_level0.bin on a 0..360s timeline. Also a final
fresh-reopen scan. No writes during the idle window.
"""
import os, sys, time, shutil, gc, glob, json
import numpy as np
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.abspath(os.path.join(HERE,".."))
os.environ.setdefault("HF_HOME", os.path.join(ROOT,"hf_cache"))
import chromadb
DIM=32; OFF=132; STRIDE=OFF+DIM*4+8
DB=os.path.join(ROOT,"db","_chroma_idle")
rng=np.random.default_rng(0)
poison=rng.standard_normal((5,DIM)).astype(np.float32)
def scan():
    segs=glob.glob(DB+"/**/data_level0.bin",recursive=True)
    files=[f for f in glob.glob(DB+"/**/*",recursive=True) if os.path.isfile(f)]
    raw=b"".join(open(f,"rb").read() for f in files)
    present=sum(int(poison[k].tobytes() in raw) for k in range(5))
    dm=tot=None; sz=None
    if segs:
        data=open(segs[0],"rb").read(); sz=len(data)
        if len(data)%STRIDE==0:
            tot=len(data)//STRIDE; dm=sum(1 for i in range(tot) if data[i*STRIDE+2]&0x01)
    return present, tot, dm, sz

shutil.rmtree(DB, ignore_errors=True)
cl=chromadb.PersistentClient(path=DB); col=cl.create_collection("idle", metadata={"hnsw:space":"l2"})
col.add(ids=[f"p{i}" for i in range(5)], embeddings=poison.tolist())
col.add(ids=[f"f{i}" for i in range(2000)], embeddings=rng.standard_normal((2000,DIM)).astype(np.float32).tolist())
del col,cl; gc.collect(); cl=chromadb.PersistentClient(path=DB); col=cl.get_collection("idle")
col.delete(ids=[f"p{i}" for i in range(5)])
col.add(ids=[f"g{i}" for i in range(200)], embeddings=rng.standard_normal((200,DIM)).astype(np.float32).tolist())
del col,cl; gc.collect()
p,tot,dm,sz=scan(); print(f"[baseline on-disk] poison={p}/5 total={tot} delete_marked={dm} seg_bytes={sz}",flush=True)

# keep a client OPEN and idle; the background compaction (if any) runs in this process
cl=chromadb.PersistentClient(path=DB); col=cl.get_collection("idle"); _=col.count()
timeline=[]; prev=0
for t in [0,30,60,120,240,360]:
    if t>prev: time.sleep(t-prev); prev=t
    _=col.count()  # touch (no writes)
    p,tot,dm,sz=scan(); timeline.append((t,p,tot,dm,sz))
    print(f"[idle t={t:>3}s, client OPEN] poison={p}/5 total={tot} delete_marked={dm} seg_bytes={sz}",flush=True)
del col,cl; gc.collect()
# final fresh reopen
cl=chromadb.PersistentClient(path=DB); col=cl.get_collection("idle"); _=col.count(); del col,cl; gc.collect()
p,tot,dm,sz=scan(); print(f"[after fresh reopen] poison={p}/5 total={tot} delete_marked={dm} seg_bytes={sz}",flush=True)
purged=next((t for t,p,tot,dm,sz in timeline if p==0), None)
out={"engine":"chromadb "+chromadb.__version__,"test":"idle background-compaction over 360s, client open",
     "baseline_present":timeline[0][1],
     "timeline":[{"t_s":t,"poison_present":p,"total":tot,"delete_marked":dm,"seg_bytes":sz} for t,p,tot,dm,sz in timeline],
     "purged_at_s":purged,
     "verdict":(f"purged at ~{purged}s (headline collapses)" if purged is not None else "NOT purged after 360s idle — Chroma uniquely never-purges holds")}
json.dump(out, open(os.path.join(ROOT,"results","phase16_chroma_idle.json"),"w"), indent=2)
print("[VERDICT]", out["verdict"],flush=True)
shutil.rmtree(DB, ignore_errors=True)
