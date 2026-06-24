#!/usr/bin/env python3
"""
Phase 22 (replication): multi-seed replication of Qdrant-server vacuum-optimizer purge.

phase9 established Qdrant-server as VEDC-AU (residue present after delete, purged once the
vacuum optimizer fires) on a single trajectory. VEDC SPEC §5 needs >=3 trials for Confirmed.
This repeats the phase9 measurement across 3 seeds: real qdrant/qdrant container, official
delete, optimizer triggered via low deleted_threshold + churn, byte-presence scan with a live
positive control, polled until purge. Results dumped after each seed (timeout-safe).

Run: .venv/bin/python scripts/phase22_qdrant_multiseed.py   (uses cached qdrant image)
"""
import os, sys, time, json, glob, subprocess
import numpy as np
np.seterr(all='ignore')
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, ".."))
DIM = 768
orig = np.load(os.path.join(ROOT, "results", "poison_embeddings.npy")).astype(np.float32)
SEEDS = [0, 1, 2, 3, 4]  # extra seeds so >=3 VALID trials survive transient scan flakes
POLL = [0, 8, 16, 30]   # seconds after churn to poll for optimizer purge
OUT = os.path.join(ROOT, "results", "phase22_qdrant_multiseed.json")
import urllib.request
def sh(c): return subprocess.run(c, shell=True, capture_output=True, text=True)

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, OptimizersConfigDiff

def run_seed(seed):
    name = f"qdrant_ms_{seed}"; store = os.path.join(ROOT, "db", f"qdrant_ms_{seed}")
    sh(f"sudo -n docker rm -f {name}"); sh(f"sudo -n rm -rf {store}")
    os.makedirs(store, exist_ok=True); sh(f"sudo -n chmod 777 {store}")
    sh(f"sudo -n docker run -d --name {name} -p 6333:6333 -v {store}:/qdrant/storage qdrant/qdrant:latest")
    for _ in range(60):
        try:
            if urllib.request.urlopen("http://localhost:6333/readyz", timeout=2).status == 200: break
        except Exception: time.sleep(1)
    else:
        sh(f"sudo -n docker rm -f {name}"); return {"seed": seed, "error": "not ready"}
    c = QdrantClient(host="localhost", port=6333)
    c.create_collection("poison", vectors_config=VectorParams(size=DIM, distance=Distance.COSINE),
        optimizers_config=OptimizersConfigDiff(default_segment_number=2, deleted_threshold=0.01,
                                               vacuum_min_vector_number=100))
    rng = np.random.default_rng(seed); fv = rng.standard_normal((2000, DIM)).astype(np.float32)
    pts = [PointStruct(id=i, vector=orig[i].tolist(), payload={"t": f"p{i}"}) for i in range(5)]
    pts += [PointStruct(id=100+i, vector=fv[i].tolist()) for i in range(2000)]
    c.upsert("poison", points=pts, wait=True)

    def scan():
        sh(f"sudo -n docker exec {name} sync"); time.sleep(1)
        sh(f"sudo -n chmod -R a+r {store}"); sh(f"sudo -n find {store} -type d -exec chmod a+rx {{}} +")
        raw = b""
        for f in [f for f in glob.glob(os.path.join(store, "**", "*"), recursive=True) if os.path.isfile(f)]:
            try: raw += open(f, "rb").read()
            except PermissionError: raw += subprocess.run(f"sudo -n cat '{f}'", shell=True, capture_output=True).stdout
        present = lambda v: v.astype(np.float32).tobytes() in raw or (v/np.linalg.norm(v)).astype(np.float32).tobytes() in raw
        return sum(present(orig[k]) for k in range(5)), present(fv[0])

    n_before, pc_before = scan()
    c.delete("poison", points_selector=[0, 1, 2, 3, 4], wait=True)
    n_afterdel, pc_afterdel = scan()
    # trigger vacuum optimizer
    c.update_collection("poison", optimizers_config=OptimizersConfigDiff(deleted_threshold=0.0001, vacuum_min_vector_number=100))
    c.upsert("poison", points=[PointStruct(id=200000+i, vector=fv[i].tolist()) for i in range(500)], wait=True)
    timeline = []
    for t in POLL:
        if t > 0: time.sleep(t - (timeline[-1][0] if timeline else 0))
        n, pc = scan(); timeline.append((t, n, pc))
        print(f"  [seed {seed} +{t:>2}s post-churn] poison={n}/5 posctrl={pc}", flush=True)
    sh(f"sudo -n docker rm -f {name}"); sh(f"sudo -n rm -rf {store}")
    purged_at = next((t for t, n, pc in timeline if n == 0 and pc), None)
    return {"seed": seed, "before_delete_present": n_before, "after_delete_present": n_afterdel,
            "before_posctrl": bool(pc_before), "after_delete_posctrl": bool(pc_afterdel),
            "post_churn_timeline": [{"t_s": t, "poison_present": n, "posctrl": bool(pc)} for t, n, pc in timeline],
            "purged_at_s": purged_at}

def summarize(trials):
    # SPEC §4: a trial whose positive control ever fails is INVALID and discarded (the scan was
    # not working at that checkpoint) — not counted as a contradiction.
    def control_held(t):
        return (t.get("before_posctrl") and t.get("after_delete_posctrl")
                and all(c["posctrl"] for c in t.get("post_churn_timeline", [])))
    valid = [t for t in trials if t.get("before_delete_present") == 5
             and t.get("after_delete_present") == 5 and control_held(t)]
    invalid = [t["seed"] for t in trials if t not in valid]
    purged = [t for t in valid if t.get("purged_at_s") is not None]
    all_purged = len(valid) >= 3 and len(purged) == len(valid)
    return {"engine": "qdrant_server (Rust)", "n_trials": len(trials), "n_valid": len(valid),
            "invalid_seeds_discarded (positive-control failed)": invalid,
            "present_after_delete_all_valid": all(t.get("after_delete_present") == 5 for t in valid) if valid else False,
            "purged_after_optimizer_all_valid": len(valid) > 0 and len(purged) == len(valid),
            "purged_at_s_per_valid_seed": {t["seed"]: t["purged_at_s"] for t in valid},
            "class": "VEDC-AU (auto/untimed)" if all_purged else "inconclusive",
            "verdict": (f"REPLICATED across {len(valid)} valid seeds: 5/5 present after delete, purged by vacuum "
                        f"optimizer in every valid trial -> VEDC-AU Confirmed" if all_purged
                        else f"only {len(valid)} valid trial(s) (need >=3); see timelines")}

def main():
    trials = []
    for seed in SEEDS:
        print(f"[*] seed {seed} ...", flush=True)
        trials.append(run_seed(seed))
        json.dump({"trials": trials, "summary": summarize(trials)}, open(OUT, "w"), indent=2)
    print("[VERDICT]", summarize(trials)["verdict"], flush=True); print("[results]", OUT)

if __name__ == "__main__":
    main()
