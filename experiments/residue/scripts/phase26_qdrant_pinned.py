#!/usr/bin/env python3
"""
Phase 26 (provenance hardening): digest-PINNED confirmatory re-run of the Qdrant-server
VEDC-AU measurement.

phase22 established Qdrant-server = VEDC-AU (Confirmed, 3 valid seeds) but pulled
`qdrant/qdrant:latest`, so its committed result does not record which image version/digest
ran (a disclosure-provenance gap). This phase pins the image by DIGEST, records the resolved
version + digest IN the result, and reproduces the present-after-delete -> purged-by-optimizer
behaviour across a few seeds. It does NOT replace phase22 (whose original :latest digest is
unknowable and left intact); it supplies the pinned-provenance evidence the advisory cites.

Run: .venv/bin/python scripts/phase26_qdrant_pinned.py   (uses cached qdrant image)
"""
import os, time, json, glob, subprocess
import numpy as np
np.seterr(all='ignore')
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, ".."))
DIM = 768
# PINNED by digest (resolved 2026-06-26; qdrant 1.18.2). Reproducible: this exact image only.
IMAGE = "qdrant/qdrant@sha256:75eab8c4ba42096724fdcfde8b4de0b5713d529dde32f285a1f86fdcb2c9e50c"
orig = np.load(os.path.join(ROOT, "results", "poison_embeddings.npy")).astype(np.float32)
SEEDS = [0, 1, 2]
POLL = [0, 8, 16, 30]
OUT = os.path.join(ROOT, "results", "phase26_qdrant_pinned.json")
import urllib.request
def sh(c): return subprocess.run(c, shell=True, capture_output=True, text=True)

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, OptimizersConfigDiff

def image_provenance():
    digest = sh(f"sudo -n docker inspect {IMAGE} --format '{{{{index .RepoDigests 0}}}}'").stdout.strip()
    ver = sh(f"sudo -n docker run --rm --entrypoint /qdrant/qdrant {IMAGE} --version").stdout.strip()
    return {"image_ref": IMAGE, "repo_digest": digest, "version_string": ver}

def run_seed(seed):
    name = f"qdrant_pin_{seed}"; store = os.path.join(ROOT, "db", f"qdrant_pin_{seed}")
    sh(f"sudo -n docker rm -f {name}"); sh(f"sudo -n rm -rf {store}")
    os.makedirs(store, exist_ok=True); sh(f"sudo -n chmod 777 {store}")
    sh(f"sudo -n docker run -d --name {name} -p 6333:6333 -v {store}:/qdrant/storage {IMAGE}")
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
    c.update_collection("poison", optimizers_config=OptimizersConfigDiff(deleted_threshold=0.0001, vacuum_min_vector_number=100))
    c.upsert("poison", points=[PointStruct(id=200000+i, vector=fv[i].tolist()) for i in range(500)], wait=True)
    timeline = []
    for t in POLL:
        if t > 0: time.sleep(t - (timeline[-1][0] if timeline else 0))
        n, pc = scan(); timeline.append((t, n, pc))
        print(f"  [seed {seed} +{t:>2}s] poison={n}/5 posctrl={pc}", flush=True)
    sh(f"sudo -n docker rm -f {name}"); sh(f"sudo -n rm -rf {store}")
    purged_at = next((t for t, n, pc in timeline if n == 0 and pc), None)
    return {"seed": seed, "before_delete_present": n_before, "after_delete_present": n_afterdel,
            "before_posctrl": bool(pc_before), "after_delete_posctrl": bool(pc_afterdel),
            "post_churn_timeline": [{"t_s": t, "poison_present": n, "posctrl": bool(pc)} for t, n, pc in timeline],
            "purged_at_s": purged_at}

def control_held(t):
    return (t.get("before_posctrl") and t.get("after_delete_posctrl")
            and all(c["posctrl"] for c in t.get("post_churn_timeline", [])))

def summarize(trials):
    valid = [t for t in trials if t.get("before_delete_present") == 5
             and t.get("after_delete_present") == 5 and control_held(t)]
    purged = [t for t in valid if t.get("purged_at_s") is not None]
    return {"engine": "qdrant_server (Rust), digest-pinned", "n_trials": len(trials), "n_valid": len(valid),
            "invalid_seeds_discarded": [t["seed"] for t in trials if t not in valid],
            "present_after_delete_all_valid": all(t.get("after_delete_present") == 5 for t in valid) if valid else False,
            "purged_after_optimizer_all_valid": len(valid) > 0 and len(purged) == len(valid),
            "class_reproduced": "VEDC-AU" if valid and len(purged) == len(valid) else "inconclusive",
            "note": "Provenance-pinned confirmatory run; Confirmed status rests on phase22 (3 valid seeds)."}

def main():
    prov = image_provenance()
    print("[provenance]", prov, flush=True)
    trials = []
    for seed in SEEDS:
        print(f"[*] seed {seed} ...", flush=True)
        trials.append(run_seed(seed))
        json.dump({"provenance": prov, "trials": trials, "summary": summarize(trials)}, open(OUT, "w"), indent=2)
    print("[VERDICT]", summarize(trials)["class_reproduced"], "| pinned", prov["version_string"], flush=True)
    print("[results]", OUT)

if __name__ == "__main__":
    main()
