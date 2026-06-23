#!/usr/bin/env python3
"""
Phase 10: Weaviate (real Go engine, LSM-tree storage + HNSW commitlog) deletion residue.
New storage class vs the others. Runs the weaviate container, mounts data dir, inserts
vectors (vectorizer:none), deletes, and scans LSM/HNSW files for raw float32 residue with
a live-filler positive control, before/after delete and after a tombstone-cleanup wait.
"""
import os, sys, time, json, glob, subprocess, urllib.request
import numpy as np
np.seterr(all='ignore')
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.abspath(os.path.join(HERE,".."))
DATA=os.path.join(ROOT,"db","weaviate_data"); NAME="weav_res"; DIM=768
orig=np.load(os.path.join(ROOT,"results","poison_embeddings.npy")).astype(np.float32)
orig_n=orig/np.linalg.norm(orig,axis=1,keepdims=True)
def sh(c): return subprocess.run(c,shell=True,capture_output=True,text=True)
def req(method,url,body=None):
    data=json.dumps(body).encode() if body is not None else None
    r=urllib.request.Request(url,data=data,method=method,headers={"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(r,timeout=30) as resp: return resp.status, resp.read()
    except urllib.error.HTTPError as e: return e.code, e.read()

sh(f"sudo -n docker rm -f {NAME}"); sh(f"sudo -n rm -rf {DATA}"); os.makedirs(DATA,exist_ok=True); sh(f"sudo -n chmod 777 {DATA}")
print("[*] starting weaviate...",flush=True)
r=sh(f"sudo -n docker run -d --name {NAME} -p 8080:8080 -p 50051:50051 "
     f"-e AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true -e PERSISTENCE_DATA_PATH=/var/lib/weaviate "
     f"-e DEFAULT_VECTORIZER_MODULE=none -e ENABLE_MODULES='' "
     f"-v {DATA}:/var/lib/weaviate cr.weaviate.io/semitechnologies/weaviate:1.28.2")
print("   ",r.stdout.strip()[:20] or r.stderr.strip()[:200],flush=True)
for _ in range(90):
    try:
        s,_=req("GET","http://localhost:8080/v1/.well-known/ready")
        if s==200: break
    except Exception: pass
    time.sleep(1)
else: print("weaviate not ready"); sys.exit(1)
print("[*] weaviate ready",flush=True)

req("POST","http://localhost:8080/v1/schema",{"class":"Poison","vectorizer":"none",
    "properties":[{"name":"t","dataType":["text"]}]})
import uuid
def uid(i): return str(uuid.UUID(int=i))
rng=np.random.default_rng(0); fv=rng.standard_normal((300,DIM)).astype(np.float32)
fv/=np.linalg.norm(fv,axis=1,keepdims=True)
objs=[{"class":"Poison","id":uid(i),"vector":orig[i].tolist(),"properties":{"t":f"poison{i}"}} for i in range(5)]
objs+=[{"class":"Poison","id":uid(1000+i),"vector":fv[i].tolist(),"properties":{"t":f"benign{i}"}} for i in range(300)]
for c in range(0,len(objs),100):
    req("POST","http://localhost:8080/v1/batch/objects",{"objects":objs[c:c+100]})
time.sleep(2)
s,b=req("GET","http://localhost:8080/v1/objects?class=Poison&limit=1")
print("[*] inserted; sample status",s,flush=True)

def scan(tag):
    sh(f"sudo -n docker exec {NAME} sync"); time.sleep(2)
    sh(f"sudo -n chmod -R a+rX {DATA}")
    files=[f for f in glob.glob(os.path.join(DATA,"**","*"),recursive=True) if os.path.isfile(f)]
    raw=b""
    for f in files:
        try: raw+=open(f,"rb").read()
        except Exception: raw+=subprocess.run(f"sudo -n cat '{f}'",shell=True,capture_output=True).stdout
    def present(v): return v.astype(np.float32).tobytes() in raw or (v/np.linalg.norm(v)).astype(np.float32).tobytes() in raw
    exact=[present(orig[k]) for k in range(5)]; pc=present(fv[0])
    print(f"[{tag}] store_bytes={len(raw)} poison_present={exact} n={sum(exact)} POSCTRL_filler={pc}",flush=True)
    return exact

scan("BEFORE_delete")
for i in range(5):
    req("DELETE",f"http://localhost:8080/v1/objects/Poison/{uid(i)}")
time.sleep(2)
s,b=req("GET","http://localhost:8080/v1/objects/Poison/"+uid(0))
print("[*] deleted poison; GET deleted id status=",s,flush=True)
scan("AFTER_delete")
# churn + wait to let async tombstone cleanup / compaction run
for c in range(0,300,100):
    req("POST","http://localhost:8080/v1/batch/objects",{"objects":[{"class":"Poison","id":uid(5000+c+i),"vector":fv[i].tolist(),"properties":{"t":f"x{i}"}} for i in range(100)]})
time.sleep(20)
scan("AFTER_churn_wait")
sh(f"sudo -n docker rm -f {NAME}"); print("[stopped]",flush=True)
