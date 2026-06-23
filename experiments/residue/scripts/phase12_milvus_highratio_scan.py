#!/usr/bin/env python3
"""Phase 12 inner: Milvus HIGH delete-ratio purge confirmation.
Deletes 1200/3005 (~40% > the 20% single-segment compaction threshold) including the 5
poison, then compact + GC wait. If the threshold hypothesis holds, compaction rewrites the
segment dropping deleted rows and GC removes the old one -> poison purged from MinIO."""
import os, time, glob, subprocess
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
idx=c.prepare_index_params(); idx.add_index(field_name="vector", index_type="HNSW", metric_type="L2",
                                            params={"M":16,"efConstruction":200})
c.create_index("poison", idx); c.load_collection("poison")
rng=np.random.default_rng(0); fv=rng.standard_normal((3000,DIM)).astype(np.float32)
data=[{"id":i,"vector":orig[i].tolist()} for i in range(5)]
data+=[{"id":100+i,"vector":fv[i].tolist()} for i in range(3000)]
c.insert("poison", data); c.flush("poison")
print("[*] inserted count=", c.query("poison", filter="", output_fields=["count(*)"]), flush=True)

def scan(tag):
    subprocess.run("sudo -n chmod -R a+rX "+MINIO, shell=True)
    files=[f for f in glob.glob(os.path.join(MINIO,"**","*"),recursive=True) if os.path.isfile(f)]
    raw=b""
    for f in files:
        try: raw+=open(f,"rb").read()
        except Exception: raw+=subprocess.run(f"sudo -n cat '{f}'",shell=True,capture_output=True).stdout
    exact=[orig[k].tobytes() in raw for k in range(5)]; pc=fv[0].tobytes() in raw
    print(f"[{tag}] minio_bytes={len(raw)} poison_present={exact} n={sum(exact)} POSCTRL_filler={pc}", flush=True)
    return exact

scan("BEFORE_delete")
# HIGH ratio: delete 5 poison + 1195 filler = 1200/3005 ~ 40%
del_ids=[0,1,2,3,4]+[100+i for i in range(1195)]
c.delete("poison", ids=del_ids); c.flush("poison")
time.sleep(2)
print("[*] deleted", len(del_ids), "of 3005 (~40%); logical poison q:", c.query("poison", filter="id < 5", output_fields=["id"]), flush=True)
scan("AFTER_delete")
print("[*] compacting...", flush=True)
jid=c.compact("poison")
for _ in range(40):
    try:
        st=c.get_compaction_state(jid)
        if "Completed" in str(st) or "completed" in str(st): print("   compaction:", st, flush=True); break
    except Exception as e: print("   state err", e, flush=True); break
    time.sleep(3)
scan("AFTER_compact")
print("[*] waiting for GC (interval 30s)...", flush=True)
time.sleep(80)
scan("AFTER_gc_wait")
