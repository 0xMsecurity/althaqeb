#!/usr/bin/env python3
"""
Phase 25 (new engine): LanceDB deletion residue (versioned columnar Lance format).

LanceDB stores rows in immutable fragments under a versioned dataset; delete() writes a new
version with a deletion file (soft delete) and leaves the fragment data in place. The hypothesis
is therefore VEDC-M-like: residue persists after delete and is purged only by explicit
compaction + old-version cleanup (no automatic background reclamation by default). 10th engine
for the registry; a real production vector DB with a reclamation model the registry lacks.

Method: insert 5 fixed poison vectors + N seeded filler, delete the 5, then compact + prune old
versions. At each checkpoint scan the dataset files for exact float32 presence (raw + normalized)
with a live positive control. Multi-seed (3). Emits results/phase25_lancedb.json.
"""
import os, glob, json, shutil
from datetime import timedelta
import numpy as np
import lancedb
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, ".."))
DIM = 768
orig = np.load(os.path.join(ROOT, "results", "poison_embeddings.npy")).astype(np.float32)
SEEDS = [0, 1, 2]

def scan(dbdir, fv):
    files = [f for f in glob.glob(os.path.join(dbdir, "**", "*"), recursive=True) if os.path.isfile(f)]
    raw = b""
    for f in files:
        try: raw += open(f, "rb").read()
        except Exception: pass
    pres = lambda v: v.astype(np.float32).tobytes() in raw or (v/np.linalg.norm(v)).astype(np.float32).tobytes() in raw
    return sum(pres(orig[k]) for k in range(5)), bool(pres(fv[0])), len(raw)

def _optimize(tbl):
    try:
        tbl.optimize(cleanup_older_than=timedelta(seconds=0))
    except Exception:
        try: tbl.compact_files()
        except Exception: pass
        try: tbl.cleanup_old_versions(older_than=timedelta(seconds=0), delete_unverified=True)
        except Exception: pass

def run_seed(seed):
    # Progression that characterizes LanceDB's reclamation: soft-delete -> optimize at LOW ratio
    # (deletion not materialized) -> optimize at HIGH ratio (materialized). Positive control is a
    # live filler (id 100) that is NEVER deleted.
    dbdir = os.path.join(ROOT, "db", f"_lancedb_seed{seed}")
    shutil.rmtree(dbdir, ignore_errors=True)
    db = lancedb.connect(dbdir)
    rng = np.random.default_rng(seed); fv = rng.standard_normal((500, DIM)).astype(np.float32)
    data = [{"id": i, "vector": orig[i].tolist()} for i in range(5)]
    data += [{"id": 100 + i, "vector": fv[i].tolist()} for i in range(500)]
    tbl = db.create_table("t", data=data)
    cps = {}
    n, pc, b = scan(dbdir, fv); cps["BEFORE_delete"] = {"poison_present": n, "posctrl": pc, "bytes": b}
    tbl.delete("id < 5")                                   # low ratio: 5 / 505 ≈ 1%
    n, pc, b = scan(dbdir, fv); cps["AFTER_delete_lowratio"] = {"poison_present": n, "posctrl": pc, "bytes": b, "logical_rows": tbl.count_rows()}
    _optimize(tbl)
    n, pc, b = scan(dbdir, fv); cps["AFTER_optimize_lowratio"] = {"poison_present": n, "posctrl": pc, "bytes": b}
    tbl.delete("id >= 200 and id < 400")                   # push deletion ratio high (~40%); id 100 stays live
    _optimize(tbl)
    n, pc, b = scan(dbdir, fv); cps["AFTER_optimize_highratio"] = {"poison_present": n, "posctrl": pc, "bytes": b, "logical_rows": tbl.count_rows()}
    shutil.rmtree(dbdir, ignore_errors=True)
    return {"seed": seed, "checkpoints": cps}

def summarize(trials):
    def held(t): return all(c["posctrl"] for c in t["checkpoints"].values())
    valid = [t for t in trials if t["checkpoints"]["BEFORE_delete"]["poison_present"] == 5 and held(t)]
    if not valid:
        return {"engine": "lancedb 0.33.0", "n_valid": 0,
                "before_present_per_seed": [t["checkpoints"]["BEFORE_delete"]["poison_present"] for t in trials],
                "verdict": "no valid trials (before-delete < 5/5 or positive control failed) — detector may not fit"}
    a_del = [t["checkpoints"]["AFTER_delete_lowratio"]["poison_present"] for t in valid]
    a_low = [t["checkpoints"]["AFTER_optimize_lowratio"]["poison_present"] for t in valid]
    a_high = [t["checkpoints"]["AFTER_optimize_highratio"]["poison_present"] for t in valid]
    persists_softdelete = all(x == 5 for x in a_del)
    persists_lowratio_optimize = all(x == 5 for x in a_low)
    purged_highratio_optimize = all(x == 0 for x in a_high)
    if persists_softdelete and persists_lowratio_optimize and purged_highratio_optimize:
        wc = "manual-only"
        v = (f"REPLICATED across {len(valid)} seeds: soft delete leaves residue (5/5); a routine optimize at "
             f"LOW delete ratio does NOT purge it (5/5 — deletion not materialized, like Milvus small-ratio); "
             f"only explicit compaction at HIGH delete ratio materializes + purges (0/5). -> VEDC-M+S "
             f"(manual, deletion-materialization-threshold-gated; deletion self-identifies via Lance deletion files).")
    elif persists_softdelete and not purged_highratio_optimize:
        wc = "unbounded?"; v = f"present after delete AND after high-ratio optimize: {a_high}"
    else:
        wc = "partial"; v = f"after_delete {a_del} / opt_low {a_low} / opt_high {a_high}"
    return {"engine": "lancedb 0.33.0", "n_valid": len(valid), "self_identifying_deletion": True,
            "poison_after_softdelete": a_del, "poison_after_optimize_lowratio": a_low,
            "poison_after_optimize_highratio": a_high, "window_class_observed": wc, "verdict": v}

def main():
    trials = [run_seed(s) for s in SEEDS]
    for t in trials:
        cp = t["checkpoints"]
        print(f"seed {t['seed']}: before={cp['BEFORE_delete']['poison_present']}/5 "
              f"after_softdelete={cp['AFTER_delete_lowratio']['poison_present']}/5 "
              f"after_opt_lowratio={cp['AFTER_optimize_lowratio']['poison_present']}/5 "
              f"after_opt_highratio={cp['AFTER_optimize_highratio']['poison_present']}/5 "
              f"posctrl={all(c['posctrl'] for c in cp.values())}", flush=True)
    out = {"trials": trials, "summary": summarize(trials)}
    json.dump(out, open(os.path.join(ROOT, "results", "phase25_lancedb.json"), "w"), indent=2)
    print("[VERDICT]", out["summary"]["verdict"], flush=True)

if __name__ == "__main__":
    main()
