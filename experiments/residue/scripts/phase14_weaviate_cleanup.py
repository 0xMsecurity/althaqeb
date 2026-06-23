#!/usr/bin/env python3
"""
Phase 14 (self-falsification): does Weaviate's tombstone cleanup eventually PURGE the deleted
vector from disk? phase10 only showed "persists >= 20s". Here we set the HNSW
`cleanupIntervalSeconds` LOW (5s) and scan on a timeline to find the purge point (or confirm
durability over minutes). Finding the purge point is a success (bounds the claim honestly).
"""
import os, sys, time, json, glob, subprocess
import numpy as np
np.seterr(all='ignore')
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.abspath(os.path.join(HERE,".."))
DATA=os.path.join(ROOT,"db","weaviate_cln"); NAME="weav_cln"; DIM=768
orig=np.load(os.path.join(ROOT,"results","poison_embeddings.npy")).astype(np.float32)
def sh(c): return subprocess.run(c,shell=True,capture_output=True,text=True)
import urllib.request
def req(method,url,body=None):
    data=json.dumps(body).encode() if body is not None else None
    r=urllib.request.Request(url,data=data,method=method,headers={"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(r,timeout=30) as resp: return resp.status, resp.read()
    except urllib.error.HTTPError as e: return e.code, e.read()

sh(f"sudo -n docker rm -f {NAME}"); sh(f"sudo -n rm -rf {DATA}"); os.makedirs(DATA,exist_ok=True); sh(f"sudo -n chmod 777 {DATA}")
print("[*] starting weaviate (low cleanup interval)...",flush=True)
sh(f"sudo -n docker run -d --name {NAME} -p 8090:8080 "
   f"-e AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true -e PERSISTENCE_DATA_PATH=/var/lib/weaviate "
   f"-e DEFAULT_VECTORIZER_MODULE=none -e ENABLE_MODULES='' "
   f"-v {DATA}:/var/lib/weaviate cr.weaviate.io/semitechnologies/weaviate:1.28.2")
for _ in range(90):
    try:
        s,_=req("GET","http://localhost:8090/v1/.well-known/ready")
        if s==200: break
    except Exception: pass
    time.sleep(1)
else: print("not ready"); sys.exit(1)
print("[*] ready",flush=True)
# class with aggressive tombstone cleanup
req("POST","http://localhost:8090/v1/schema",{"class":"P","vectorizer":"none",
    "vectorIndexConfig":{"cleanupIntervalSeconds":5},"properties":[{"name":"t","dataType":["text"]}]})
import uuid
def uid(i): return str(uuid.UUID(int=i))
rng=np.random.default_rng(0); fv=rng.standard_normal((200,DIM)).astype(np.float32); fv/=np.linalg.norm(fv,axis=1,keepdims=True)
objs=[{"class":"P","id":uid(i),"vector":orig[i].tolist(),"properties":{"t":f"p{i}"}} for i in range(5)]
objs+=[{"class":"P","id":uid(1000+i),"vector":fv[i].tolist(),"properties":{"t":f"b{i}"}} for i in range(200)]
for c in range(0,len(objs),100): req("POST","http://localhost:8090/v1/batch/objects",{"objects":objs[c:c+100]})
time.sleep(2)
def scan():
    sh(f"sudo -n docker exec {NAME} sync"); sh(f"sudo -n chmod -R a+rX {DATA}")
    files=[f for f in glob.glob(os.path.join(DATA,"**","*"),recursive=True) if os.path.isfile(f)]
    raw=b""
    for f in files:
        try: raw+=open(f,"rb").read()
        except Exception: raw+=subprocess.run(f"sudo -n cat '{f}'",shell=True,capture_output=True).stdout
    pres=lambda v: v.astype(np.float32).tobytes() in raw or (v/np.linalg.norm(v)).astype(np.float32).tobytes() in raw
    return sum(pres(orig[k]) for k in range(5)), pres(fv[0]), len(raw)
n,pc,b=scan(); print(f"[t=before_delete] poison={n}/5 filler_posctrl={pc} bytes={b}",flush=True)
for i in range(5): req("DELETE",f"http://localhost:8090/v1/objects/P/{uid(i)}")
print("[*] deleted 5; observing cleanup timeline (cleanupIntervalSeconds=5)...",flush=True)
timeline=[]
for t in [0,10,20,40,70,110,160]:
    if t>0: time.sleep(t-timeline[-1][0] if timeline else t)
    n,pc,b=scan(); timeline.append((t,n,pc,b))
    print(f"[t={t:>3}s post-delete] poison={n}/5 filler_posctrl={pc} bytes={b}",flush=True)
sh(f"sudo -n docker rm -f {NAME}")
purged_at=next((t for t,n,pc,b in timeline if n==0 and pc), None)
out={"engine":"weaviate 1.28.2","cleanupIntervalSeconds":5,
     "timeline":[{"t_s":t,"poison_present":n,"posctrl":pc,"bytes":b} for t,n,pc,b in timeline],
     "purged_at_s":purged_at,
     "verdict":(f"purged at ~{purged_at}s" if purged_at is not None else "NOT purged within observed window")}
json.dump(out, open(os.path.join(ROOT,"results","phase14_weaviate_cleanup.json"),"w"), indent=2)
print("[VERDICT]", out["verdict"],flush=True)
sh(f"sudo -n rm -rf {DATA}")
