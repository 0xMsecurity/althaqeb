#!/usr/bin/env python3
"""
Phase 9: REAL Qdrant server (Rust engine) deletion residue.

The phase3 Qdrant negative was the toy in-process Python impl. This runs the actual
qdrant/qdrant container, mounts its storage to a host dir, and scans the real segment
files after an official delete (+ optimizer trigger) for raw float32 residue, with a
live-filler positive control.

Run via: sudo (docker) -- this script shells out to `sudo docker`.
"""
import os, sys, time, subprocess, glob
import numpy as np
np.seterr(all='ignore')  # misaligned float-window parsing overflows are expected noise
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.abspath(os.path.join(HERE,".."))
STORE=os.path.join(ROOT,"db","qdrant_server_storage")
NAME="qdrant_res"; DIM=768
orig=np.load(os.path.join(ROOT,"results","poison_embeddings.npy")).astype(np.float32)
orig_n=orig/np.linalg.norm(orig,axis=1,keepdims=True)

def sh(c): return subprocess.run(c,shell=True,capture_output=True,text=True)
sh(f"sudo -n docker rm -f {NAME}"); sh(f"sudo -n rm -rf {STORE}"); os.makedirs(STORE,exist_ok=True)
sh(f"sudo -n chmod 777 {STORE}")
print("[*] starting qdrant container...")
r=sh(f"sudo -n docker run -d --name {NAME} -p 6333:6333 -v {STORE}:/qdrant/storage qdrant/qdrant:latest")
print("   ", r.stdout.strip()[:20] or r.stderr.strip()[:200])
# wait ready
import urllib.request
for _ in range(60):
    try:
        if urllib.request.urlopen("http://localhost:6333/readyz",timeout=2).status==200: break
    except Exception: time.sleep(1)
else:
    print("qdrant not ready"); sys.exit(1)
print("[*] qdrant ready")

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, OptimizersConfigDiff
c=QdrantClient(host="localhost",port=6333)
c.create_collection("poison", vectors_config=VectorParams(size=DIM,distance=Distance.COSINE),
                    optimizers_config=OptimizersConfigDiff(default_segment_number=2, deleted_threshold=0.01,
                                                           vacuum_min_vector_number=100))
rng=np.random.default_rng(0); fv=rng.standard_normal((2000,DIM)).astype(np.float32)
pts=[PointStruct(id=i,vector=orig[i].tolist(),payload={"t":f"poison{i}"}) for i in range(5)]
pts+=[PointStruct(id=100+i,vector=fv[i].tolist()) for i in range(2000)]
c.upsert("poison",points=pts,wait=True)
print("[*] upserted; count=", c.count("poison").count)

def snapshot_scan(tag):
    # force flush to disk
    sh(f"sudo -n docker exec {NAME} sync")
    time.sleep(2)
    sh(f"sudo -n chmod -R a+r {STORE}"); sh(f"sudo -n find {STORE} -type d -exec chmod a+rx {{}} +")
    files=[f for f in glob.glob(os.path.join(STORE,"**","*"),recursive=True) if os.path.isfile(f)]
    raw=b""
    for f in files:
        try: raw+=open(f,"rb").read()
        except PermissionError:
            raw+=subprocess.run(f"sudo -n cat '{f}'",shell=True,capture_output=True).stdout
    # alignment-independent exact byte-substring search (Qdrant COSINE normalizes on
    # insert, so check raw AND normalized float32 bytes). Fast C memchr.
    def present(v):
        return v.astype(np.float32).tobytes() in raw or \
               (v/np.linalg.norm(v)).astype(np.float32).tobytes() in raw
    exact=[present(orig[k]) for k in range(5)]
    posctrl=present(fv[0])  # a live filler vector must be findable
    print(f"[{tag}] store_bytes={len(raw)} poison_bytes_present={exact} "
          f"n_present={sum(exact)} POSCTRL_filler_present={posctrl}", flush=True)
    return exact

snapshot_scan("BEFORE_delete")
c.delete("poison", points_selector=[0,1,2,3,4], wait=True)
print("[*] deleted poison; count=", c.count("poison").count)
snapshot_scan("AFTER_delete")
# trigger vacuum optimizer by updating config + churn, then wait
c.update_collection("poison", optimizers_config=OptimizersConfigDiff(deleted_threshold=0.0001, vacuum_min_vector_number=100))
# churn to trigger optimizer
c.upsert("poison",points=[PointStruct(id=200000+i,vector=fv[i].tolist()) for i in range(500)],wait=True)
time.sleep(8)
snapshot_scan("AFTER_vacuum_optimizer")
sh(f"sudo -n docker rm -f {NAME}")
print("[stopped]")
