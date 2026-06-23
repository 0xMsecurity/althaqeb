#!/usr/bin/env python3
"""
Phase 13 (self-falsification): try HARD to make ChromaDB physically reclaim deleted HNSW
vectors via the default Rust path (Local Compaction manager). White-box showed the Python
path never reclaims (replace_deleted off, mark_deleted only); the Rust compaction is a
compiled black box. If ANY of these makes the deleted vectors disappear, it is a hidden
cleanup path and a counterexample to "unbounded".

Sub-tests (each: real PersistentClient, seeded explicit embeddings, bit-identical byte search
of data_level0.bin/all files, + DELETE_MARK parse; positive control = a kept canary vector):
  A. slot-reuse: add 1000, delete 1000, add 1000 fresh  (would trigger replace_deleted reuse)
  B. 100% delete + refill x3 cycles                      (max compaction pressure)
  C. re-add the SAME deleted ids with NEW vectors        (does old vector vanish or linger?)
  D. tiny-batch churn crossing sync_threshold repeatedly (force Rust compaction passes)
Reports residue_present (deleted-known vectors still bit-identical) per sub-test.
"""
import os, sys, shutil, gc, glob, json
import numpy as np
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.abspath(os.path.join(HERE,".."))
os.environ.setdefault("HF_HOME", os.path.join(ROOT,"hf_cache"))
import chromadb
DIM=32; OFF=132; STRIDE=OFF+DIM*4+8
def newcol(db, name):
    shutil.rmtree(db, ignore_errors=True)
    cl=chromadb.PersistentClient(path=db); return cl, cl.create_collection(name, metadata={"hnsw:space":"l2"})
def reopen(db, name):
    cl=chromadb.PersistentClient(path=db); return cl, cl.get_collection(name)
def residue(db, targets):
    files=[f for f in glob.glob(db+"/**/*",recursive=True) if os.path.isfile(f)]
    raw=b"".join(open(f,"rb").read() for f in files)
    present=sum(int(t.tobytes() in raw) for t in targets)
    segs=glob.glob(db+"/**/data_level0.bin",recursive=True); dm=None; tot=None
    if segs:
        data=open(segs[0],"rb").read()
        if len(data)%STRIDE==0:
            tot=len(data)//STRIDE; dm=sum(1 for i in range(tot) if data[i*STRIDE+2]&0x01)
    return present, tot, dm

rng=np.random.default_rng(0)
out={"chromadb": chromadb.__version__, "subtests": {}}

# ---- A. slot-reuse ----
db=os.path.join(ROOT,"db","_r13a")
cl,col=newcol(db,"reclaimA")
canary=rng.standard_normal((5,DIM)).astype(np.float32)        # kept (positive control)
victims=rng.standard_normal((1000,DIM)).astype(np.float32)    # deleted
col.add(ids=[f"c{i}" for i in range(5)], embeddings=canary.tolist())
col.add(ids=[f"v{i}" for i in range(1000)], embeddings=victims.tolist())
del col,cl; gc.collect(); cl,col=reopen(db,"reclaimA")
col.delete(ids=[f"v{i}" for i in range(1000)])
fresh=rng.standard_normal((1000,DIM)).astype(np.float32)
col.add(ids=[f"n{i}" for i in range(1000)], embeddings=fresh.tolist())
del col,cl; gc.collect(); cl,col=reopen(db,"reclaimA"); _=col.count(); del col,cl; gc.collect()
vp,tot,dm=residue(db,victims); cp,_,_=residue(db,canary)
out["subtests"]["A_slot_reuse"]={"victims_present_of_1000":vp,"canary_present_of_5":cp,"total_elems":tot,"delete_marked":dm}
print("[A slot-reuse] victims_present=%d/1000 canary=%d/5 total=%s delete_marked=%s"%(vp,cp,tot,dm),flush=True)

# ---- B. 100% delete + refill x3 ----
db=os.path.join(ROOT,"db","_r13b")
cl,col=newcol(db,"reclaimB")
gen0=rng.standard_normal((1000,DIM)).astype(np.float32)
col.add(ids=[f"a{i}" for i in range(1000)], embeddings=gen0.tolist())
allgen=[gen0]
for cyc in range(3):
    del col,cl; gc.collect(); cl,col=reopen(db,"reclaimB")
    ids=[f"a{i}" for i in range(1000)] if cyc==0 else [f"r{cyc-1}_{i}" for i in range(1000)]
    col.delete(ids=ids)
    g=rng.standard_normal((1000,DIM)).astype(np.float32)
    col.add(ids=[f"r{cyc}_{i}" for i in range(1000)], embeddings=g.tolist()); allgen.append(g)
del col,cl; gc.collect()
gen0_present,tot,dm=residue(db,gen0)
out["subtests"]["B_100pct_refill_x3"]={"gen0_present_of_1000":gen0_present,"total_elems":tot,"delete_marked":dm}
print("[B 100%%-refill] gen0_present=%d/1000 total=%s delete_marked=%s"%(gen0_present,tot,dm),flush=True)

# ---- C. re-add same deleted ids with NEW vectors ----
db=os.path.join(ROOT,"db","_r13c")
cl,col=newcol(db,"reclaimC")
v1=rng.standard_normal((5,DIM)).astype(np.float32)
col.add(ids=[f"k{i}" for i in range(5)], embeddings=v1.tolist())
fill=rng.standard_normal((500,DIM)).astype(np.float32)
col.add(ids=[f"f{i}" for i in range(500)], embeddings=fill.tolist())
del col,cl; gc.collect(); cl,col=reopen(db,"reclaimC")
col.delete(ids=[f"k{i}" for i in range(5)])
v2=rng.standard_normal((5,DIM)).astype(np.float32)
col.add(ids=[f"k{i}" for i in range(5)], embeddings=v2.tolist())  # SAME ids, new vectors
for b in range(3):
    col.add(ids=[f"g{b}_{i}" for i in range(500)], embeddings=rng.standard_normal((500,DIM)).astype(np.float32).tolist())
    del col,cl; gc.collect(); cl,col=reopen(db,"reclaimC")
del col,cl; gc.collect()
old_present,tot,dm=residue(db,v1); new_present,_,_=residue(db,v2)
out["subtests"]["C_readd_same_ids"]={"old_v1_present_of_5":old_present,"new_v2_present_of_5":new_present,"total_elems":tot,"delete_marked":dm}
print("[C re-add ids] old_v1_present=%d/5 new_v2_present=%d/5 total=%s delete_marked=%s"%(old_present,new_present,tot,dm),flush=True)

# ---- D. tiny-batch churn crossing sync_threshold(=1000) ----
db=os.path.join(ROOT,"db","_r13d")
cl,col=newcol(db,"reclaimD")
mark=rng.standard_normal((5,DIM)).astype(np.float32)
col.add(ids=[f"m{i}" for i in range(5)], embeddings=mark.tolist())
col.add(ids=[f"p{i}" for i in range(1500)], embeddings=rng.standard_normal((1500,DIM)).astype(np.float32).tolist())
del col,cl; gc.collect(); cl,col=reopen(db,"reclaimD")
col.delete(ids=[f"m{i}" for i in range(5)])
for b in range(20):  # 20*200=4000 small adds, many sync_threshold crossings
    col.add(ids=[f"d{b}_{i}" for i in range(200)], embeddings=rng.standard_normal((200,DIM)).astype(np.float32).tolist())
del col,cl; gc.collect()
mp,tot,dm=residue(db,mark)
out["subtests"]["D_tinybatch_churn"]={"mark_present_of_5":mp,"total_elems":tot,"delete_marked":dm}
print("[D churn] mark_present=%d/5 total=%s delete_marked=%s"%(mp,tot,dm),flush=True)

for d in ["_r13a","_r13b","_r13c","_r13d"]: shutil.rmtree(os.path.join(ROOT,"db",d), ignore_errors=True)
verdict="NO reclaim observed (residue survived all attacks)" if all(
    out["subtests"][k].get(list(out["subtests"][k])[0],0)>0 for k in ["A_slot_reuse","B_100pct_refill_x3","C_readd_same_ids","D_tinybatch_churn"]) else "RECLAIM PATH FOUND"
out["verdict"]=verdict
json.dump(out, open(os.path.join(ROOT,"results","phase13_chroma_reclaim_attack.json"),"w"), indent=2)
print("[VERDICT]", verdict, flush=True)
