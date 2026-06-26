#!/usr/bin/env python3
"""
Phase 7: validate vecdb_residue_audit.py on a FRESH, independent Chroma DB built with
Chroma's DEFAULT embedding function (real MiniLM-L6-v2 384-d embeddings -- different
model + different dim than the gtr experiments, fully real vectors, no gaussian filler,
no crafted poison). Doubles as: (a) tool correctness, (b) replication of the residue
phenomenon on a 2nd embedding model, (c) rebuttal to synthetic-data-bias.

Steps: add 60 real docs -> delete a known 8-id subset -> compact (filler + reopen) ->
verify logical layer clean -> run auditor -> assert it finds exactly the 8 deleted.
"""
import os, sys, shutil, subprocess, json
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.abspath(os.path.join(HERE,".."))
os.environ.setdefault("HF_HOME", os.path.join(ROOT,"hf_cache"))
import chromadb

DB=os.path.join(ROOT,"db","chroma_audit_validate")
if os.path.exists(DB): shutil.rmtree(DB)

DOCS=[f"{s} {o}" for s in
 ["The patient record shows","Customer complaint regarding","Internal memo about",
  "The contract stipulates","Employee evaluation notes","The invoice total for",
  "Medical history includes","The support ticket describes","Account balance summary for",
  "The incident report details","Shipping confirmation for","The legal notice concerns"]
 for o in ["the quarterly budget.","a delayed refund.","the new data policy.","an overdue payment.","scheduled maintenance."]][:60]
SECRET=["DELETE_ME social security number 123-45-6789 belongs to john doe",
        "DELETE_ME credit card 4111 1111 1111 1111 expiry 12/29",
        "DELETE_ME home address 42 private lane, springfield, confidential",
        "DELETE_ME medical diagnosis hiv positive patient id 99812",
        "DELETE_ME password reset token a1b2c3d4e5 for admin account",
        "DELETE_ME bank routing 021000021 account 9988776655 wire ready",
        "DELETE_ME api secret sk-live-9x8y7z please rotate immediately",
        "DELETE_ME private key BEGIN RSA do not share with anyone ever"]

client=chromadb.PersistentClient(path=DB)
col=client.create_collection("records")  # DEFAULT embedding fn -> MiniLM-L6-v2, dim 384
# add benign + secret docs
ids=[f"rec{i}" for i in range(len(DOCS))]+[f"secret{i}" for i in range(len(SECRET))]
docs=DOCS+SECRET
col.add(ids=ids, documents=docs)
print("[added]", col.count(), "docs (real MiniLM embeddings)")
# the right-to-be-forgotten deletion
del_ids=[f"secret{i}" for i in range(len(SECRET))]
col.delete(ids=del_ids)
print("[deleted]", len(del_ids), "secret records; logical count now", col.count())
# compact: filler writes + reopen
import numpy as np
for b in range(4):
    col.add(ids=[f"f{b}_{i}" for i in range(500)], documents=[f"filler doc {b} {i}" for i in range(500)])
    del col, client; import gc; gc.collect()
    client=chromadb.PersistentClient(path=DB); col=client.get_collection("records")
print("[after compaction] logical count", col.count(),
      "| deleted ids still queryable?", col.get(ids=del_ids)["ids"], "(empty=clean)")
del col, client

# run the auditor as an external tool
r=subprocess.run([sys.executable, os.path.join(HERE,"vecdb_residue_audit.py"), DB],
                 capture_output=True, text=True)
print("\n========== AUDITOR OUTPUT ==========")
print(r.stdout)
print("exit code:", r.returncode)
rep=json.loads(r.stdout.split("\n\n")[0]) if r.stdout.strip().startswith("{") else None
result={
    "phase": "phase7_audit_validation",
    "purpose": "independent replication on Chroma default MiniLM-L6-v2 (dim 384) + auditor correctness",
    "embedding_model": "chroma-default all-MiniLM-L6-v2 (ONNX, dim 384)",
    "n_docs_added": len(ids),
    "expected_deleted": len(del_ids),
    "deleted_ids_logically_queryable_after_compaction": rep is None,  # overwritten below
}
if rep:
    found=rep["total_deleted_recoverable"]
    dims=[s.get("dim") for s in rep["segments"]]
    src=[s.get("dim_source") for s in rep["segments"]]
    result.update({
        "auditor_found_recoverable": found,
        "segment_dims": dims,
        "segment_dim_source": src,
        "validation": "PASS" if found==len(del_ids) else "MISMATCH",
        "exit_code": r.returncode,
        "exit_code_signals_residue": r.returncode==2,
    })
    print(f"\n[VALIDATION] expected_deleted={len(del_ids)}  auditor_found={found}  "
          f"dims={dims} source={src}")
    print(f"[VALIDATION] {result['validation']} "
          f"| exit_code_signals_residue={r.returncode==2}")
else:
    result.update({"auditor_found_recoverable": None, "validation": "NO_REPORT",
                   "exit_code": r.returncode})
    print("[VALIDATION] auditor produced no JSON report")
OUT=os.path.join(ROOT,"results","phase7_audit.json")
with open(OUT,"w") as f: json.dump(result, f, indent=2)
print("[written]", OUT)
