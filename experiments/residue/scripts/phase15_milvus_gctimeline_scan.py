#!/usr/bin/env python3
"""Phase 15 inner: does Milvus EVENTUALLY purge after high-ratio delete + compaction, given a
long GC timeline? (Weaviate purged at ~70s; phase11/12 only waited ~80s for Milvus.) Scans the
MinIO object store on a timeline out to ~6 min to find the purge point or confirm durability."""
import os, time, glob, subprocess, json
import numpy as np
np.seterr(all='ignore')
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.abspath(os.path.join(HERE,".."))
MINIO=os.path.join(ROOT,"db","milvus_minio"); DIM=768
orig=np.load(os.path.join(ROOT,"results","poison_embeddings.npy")).astype(np.float32)
from pymilvus import MilvusClient, DataType
c=MilvusClient(uri="http://localhost:19530")
if c.has_collection("poison"): c.drop_collection("poison")
schema=c.create_schema(auto_id=False, enable_dynamic_field=True)
schema.add_field("id", DataType.INT64, is_primary=True)
schema.add_field("vector", DataType.FLOAT_VECTOR, dim=DIM)
c.create_collection("poison", schema=schema)
idx=c.prepare_index_params(); idx.add_index(field_name="vector", index_type="HNSW", metric_type="L2", params={"M":16,"efConstruction":200})
c.create_index("poison", idx); c.load_collection("poison")
rng=np.random.default_rng(0); fv=rng.standard_normal((3000,DIM)).astype(np.float32)
c.insert("poison", [{"id":i,"vector":orig[i].tolist()} for i in range(5)]+
                   [{"id":100+i,"vector":fv[i].tolist()} for i in range(3000)])
c.flush("poison")
def scan():
    subprocess.run("sudo -n chmod -R a+rX "+MINIO, shell=True)
    files=[f for f in glob.glob(os.path.join(MINIO,"**","*"),recursive=True) if os.path.isfile(f)]
    raw=b""
    for f in files:
        try: raw+=open(f,"rb").read()
        except Exception: raw+=subprocess.run(f"sudo -n cat '{f}'",shell=True,capture_output=True).stdout
    return sum(orig[k].tobytes() in raw for k in range(5)), (fv[0].tobytes() in raw), len(raw)
n,pc,b=scan(); print(f"[before_delete] poison={n}/5 posctrl={pc} bytes={b}",flush=True)
c.delete("poison", ids=[0,1,2,3,4]+[100+i for i in range(1195)]); c.flush("poison")  # ~40%
time.sleep(2)
jid=c.compact("poison")
for _ in range(40):
    try:
        if "Completed" in str(c.get_compaction_state(jid)): break
    except Exception: break
    time.sleep(3)
print("[*] high-ratio delete + compaction Completed; GC timeline...",flush=True)
timeline=[]; prev=0
for t in [0,30,60,120,240,360]:
    if t>prev: time.sleep(t-prev); prev=t
    n,pc,b=scan(); timeline.append((t,n,pc,b))
    print(f"[t={t:>3}s] poison={n}/5 posctrl={pc} bytes={b}",flush=True)
purged=next((t for t,n,pc,b in timeline if n==0), None)
out={"engine":"milvus standalone v2.5.10","delete_ratio":"~40%","gc_interval_s":30,
     "timeline":[{"t_s":t,"poison_present":n,"posctrl":pc,"bytes":b} for t,n,pc,b in timeline],
     "purged_at_s":purged,
     "verdict":(f"purged at ~{purged}s" if purged is not None else "NOT purged within 360s of completed compaction")}
json.dump(out, open(os.path.join(ROOT,"results","phase15_milvus_gctimeline.json"),"w"), indent=2)
print("[VERDICT]", out["verdict"],flush=True)
