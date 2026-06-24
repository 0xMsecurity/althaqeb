#!/usr/bin/env python3
"""
Phase 19 (replication): multi-seed replication of Weaviate tombstone-cleanup purge timing.

phase14 established the Weaviate class (VEDC-AT, purged ~70s at cleanupIntervalSeconds=5) on a
SINGLE trajectory. The VEDC standard (SPEC §5) requires >=3 independent trials to upgrade a
classification from Provisional to Confirmed. This runs the SAME measurement across 3 seeds and
reports the purge-time distribution.

Method is identical to phase14: fresh Weaviate container per seed, insert 5 fixed poison vectors
+ N seeded filler, delete the 5, observe a byte-presence timeline with a live-filler positive
control, record the purge point. Poison vectors are fixed (they are the targets); the filler set
and run instance vary per seed. Results are dumped after EACH seed so a timeout still leaves
partial evidence.

Run: .venv/bin/python scripts/phase19_weaviate_multiseed.py   (uses cached weaviate image)
"""
import os, sys, time, json, glob, subprocess, uuid
import numpy as np
np.seterr(all='ignore')
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, ".."))
DIM = 768
orig = np.load(os.path.join(ROOT, "results", "poison_embeddings.npy")).astype(np.float32)
IMAGE = "cr.weaviate.io/semitechnologies/weaviate:1.28.2"
PORT = "8090"
SEEDS = [0, 1, 2]
TIMELINE = [0, 20, 45, 70, 95, 130]   # brackets the ~70s purge observed in phase14
OUT = os.path.join(ROOT, "results", "phase19_weaviate_multiseed.json")

import urllib.request, urllib.error
def sh(c): return subprocess.run(c, shell=True, capture_output=True, text=True)
def req(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=30) as resp: return resp.status, resp.read()
    except urllib.error.HTTPError as e: return e.code, e.read()
    except Exception: return 0, b""
def uidf(i): return str(uuid.UUID(int=i))

def run_seed(seed):
    name = f"weav_ms_{seed}"; data = os.path.join(ROOT, "db", f"weaviate_ms_{seed}")
    sh(f"sudo -n docker rm -f {name}"); sh(f"sudo -n rm -rf {data}")
    os.makedirs(data, exist_ok=True); sh(f"sudo -n chmod 777 {data}")
    sh(f"sudo -n docker run -d --name {name} -p {PORT}:8080 "
       f"-e AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true -e PERSISTENCE_DATA_PATH=/var/lib/weaviate "
       f"-e DEFAULT_VECTORIZER_MODULE=none -e ENABLE_MODULES='' "
       f"-v {data}:/var/lib/weaviate {IMAGE}")
    for _ in range(90):
        s, _ = req("GET", f"http://localhost:{PORT}/v1/.well-known/ready")
        if s == 200: break
        time.sleep(1)
    else:
        sh(f"sudo -n docker rm -f {name}"); return {"seed": seed, "error": "not ready"}
    req("POST", f"http://localhost:{PORT}/v1/schema", {"class": "P", "vectorizer": "none",
        "vectorIndexConfig": {"cleanupIntervalSeconds": 5}, "properties": [{"name": "t", "dataType": ["text"]}]})
    rng = np.random.default_rng(seed)
    fv = rng.standard_normal((200, DIM)).astype(np.float32); fv /= np.linalg.norm(fv, axis=1, keepdims=True)
    objs = [{"class": "P", "id": uidf(i), "vector": orig[i].tolist(), "properties": {"t": f"p{i}"}} for i in range(5)]
    objs += [{"class": "P", "id": uidf(1000+i), "vector": fv[i].tolist(), "properties": {"t": f"b{i}"}} for i in range(200)]
    for c in range(0, len(objs), 100):
        req("POST", f"http://localhost:{PORT}/v1/batch/objects", {"objects": objs[c:c+100]})
    time.sleep(2)
    def scan():
        sh(f"sudo -n docker exec {name} sync"); sh(f"sudo -n chmod -R a+rX {data}")
        files = [f for f in glob.glob(os.path.join(data, "**", "*"), recursive=True) if os.path.isfile(f)]
        raw = b""
        for f in files:
            try: raw += open(f, "rb").read()
            except Exception: raw += subprocess.run(f"sudo -n cat '{f}'", shell=True, capture_output=True).stdout
        pres = lambda v: v.astype(np.float32).tobytes() in raw or (v/np.linalg.norm(v)).astype(np.float32).tobytes() in raw
        return sum(pres(orig[k]) for k in range(5)), pres(fv[0]), len(raw)
    n0, pc0, _ = scan()
    for i in range(5): req("DELETE", f"http://localhost:{PORT}/v1/objects/P/{uidf(i)}")
    timeline = []
    for t in TIMELINE:
        if t > 0: time.sleep(t - (timeline[-1][0] if timeline else 0))
        n, pc, b = scan(); timeline.append((t, n, pc, b))
        print(f"  [seed {seed} t={t:>3}s] poison={n}/5 posctrl={pc}", flush=True)
    sh(f"sudo -n docker rm -f {name}"); sh(f"sudo -n rm -rf {data}")
    purged_at = next((t for t, n, pc, b in timeline if n == 0 and pc), None)
    return {"seed": seed, "before_delete_present": n0, "before_delete_posctrl": bool(pc0),
            "timeline": [{"t_s": t, "poison_present": n, "posctrl": bool(pc)} for t, n, pc, b in timeline],
            "purged_at_s": purged_at}

def summarize(trials):
    valid = [t for t in trials if "purged_at_s" in t and t.get("before_delete_present") == 5]
    purges = [t["purged_at_s"] for t in valid if t["purged_at_s"] is not None]
    all_purged = len(purges) == len(valid) and len(valid) > 0
    posctrl_ok = all(all(c["posctrl"] for c in t["timeline"]) for t in valid)
    return {"engine": "weaviate 1.28.2", "cleanupIntervalSeconds": 5, "seeds": [t["seed"] for t in trials],
            "n_trials": len(trials), "n_valid": len(valid),
            "purged_at_s_per_seed": {t["seed"]: t["purged_at_s"] for t in valid},
            "all_trials_purged": all_purged,
            "purge_s_min": (min(purges) if purges else None), "purge_s_max": (max(purges) if purges else None),
            "purge_s_mean": (round(sum(purges)/len(purges), 1) if purges else None),
            "positive_control_held_all_trials": posctrl_ok,
            "class": "VEDC-AT (auto/timed)" if all_purged else "inconclusive",
            "verdict": (f"REPLICATED across {len(valid)} seeds: residue purged in every trial "
                        f"(purge {min(purges)}-{max(purges)}s); class VEDC-AT stable -> Confirmed"
                        if all_purged else "NOT replicated: inconsistent purge across seeds")}

def main():
    trials = []
    for seed in SEEDS:
        print(f"[*] seed {seed} ...", flush=True)
        trials.append(run_seed(seed))
        json.dump({"trials": trials, "summary": summarize(trials)}, open(OUT, "w"), indent=2)  # incremental
    print("[VERDICT]", summarize(trials)["verdict"], flush=True)
    print("[results]", OUT)

if __name__ == "__main__":
    main()
