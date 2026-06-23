#!/usr/bin/env python3
"""
Phase 6 (Stage 9, blind attacker): the deletion marker self-identifies the residue.

Reading ONLY the raw Chroma HNSW segment data_level0.bin (no IDs, no schema, no
knowledge of which vectors were sensitive), select exactly the elements whose
hnswlib DELETE_MARK bit is set on disk, and show they are the deleted vectors.

hnswlib element block (M=16): [linkcount u16 @0][delete byte @+2 (bit0=DELETE_MARK)]
[32 links][768 float32 @+132][label u64]. STRIDE = 132 + 768*4 + 8 = 3212.

Implication beyond SIGMOD'07 "deleted records persist": deletion TAGS the residue,
so the attacker recovers exactly what was meant to be erased (and only that),
inverting 5 vectors instead of all 3005.

Cross-engine analog (already observed): Milvus delta parquet lists deleted ids;
Postgres dead tuples carry xmax. The deletion log points at the retained data.

Usage: phase6_blind_deletemark.py [path-to-data_level0.bin]
"""
import sys, glob, json, os
import numpy as np
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.abspath(os.path.join(HERE,".."))
DIM=768; OFF=132; STRIDE=OFF+DIM*4+8
seg=sys.argv[1] if len(sys.argv)>1 else glob.glob(os.path.join(ROOT,"db","chroma_gtr_seed0","*","data_level0.bin"))[0]
data=open(seg,"rb").read(); n=len(data)//STRIDE
orig=np.load(os.path.join(ROOT,"results","poison_embeddings.npy")).astype(np.float32)
orig_n=orig/np.linalg.norm(orig,axis=1,keepdims=True)
del_idx=[]; del_vecs=[]
for i in range(n):
    base=i*STRIDE
    if data[base+2] & 0x01:                      # DELETE_MARK persisted on disk
        del_idx.append(i)
        del_vecs.append(np.frombuffer(data[base+OFF:base+OFF+DIM*4],dtype=np.float32).copy())
res={"segment":seg,"total_elements":n,"delete_marked":len(del_idx),"deleted_indices":del_idx}
if del_vecs:
    D=np.stack(del_vecs); Dn=D/np.linalg.norm(D,axis=1,keepdims=True); sim=Dn@orig_n.T
    res["cosine_to_best_poison"]=[round(float(sim[j].max()),4) for j in range(len(del_vecs))]
    res["matched_poison"]=[int(sim[j].argmax()) for j in range(len(del_vecs))]
    res["all_poison_covered"]=sorted(set(res["matched_poison"]))==list(range(5))
print(json.dumps(res,indent=2))
json.dump(res,open(os.path.join(ROOT,"results","phase6_blind_deletemark.json"),"w"),indent=2)
