#!/usr/bin/env python3
"""
Phase 23 (new engine): sqlite-vec deletion residue (embedded vector search in SQLite).

sqlite-vec stores vectors in a vec0 virtual table backed by SQLite shadow tables. SQLite DELETE
frees pages without zeroing them (like a heap), so the hypothesis is: residue persists after
delete and is purged by VACUUM (which rewrites the database file). 9th engine for the registry;
multi-seed (3) inline since it is in-process and fast.

Method: insert 5 fixed poison vectors + N seeded filler, DELETE the 5, then VACUUM. At each
checkpoint scan the .db file bytes for exact float32 presence (raw + normalized) with a live
positive control. Emits results/phase23_sqlitevec.json.

Run: .venv/bin/python scripts/phase23_sqlitevec.py
"""
import os, sqlite3, json
import numpy as np
import sqlite_vec
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, ".."))
DIM = 768
orig = np.load(os.path.join(ROOT, "results", "poison_embeddings.npy")).astype(np.float32)
SEEDS = [0, 1, 2]
DBDIR = os.path.join(ROOT, "db")

def scan(dbpath, fv):
    with open(dbpath, "rb") as f:
        raw = f.read()
    pres = lambda v: v.astype(np.float32).tobytes() in raw or (v/np.linalg.norm(v)).astype(np.float32).tobytes() in raw
    return sum(pres(orig[k]) for k in range(5)), bool(pres(fv[0])), len(raw)

def run_seed(seed):
    dbpath = os.path.join(DBDIR, f"_sqlitevec_seed{seed}.db")
    if os.path.exists(dbpath): os.remove(dbpath)
    con = sqlite3.connect(dbpath); con.enable_load_extension(True); sqlite_vec.load(con); con.enable_load_extension(False)
    con.execute(f"CREATE VIRTUAL TABLE v USING vec0(embedding float[{DIM}])")
    rng = np.random.default_rng(seed); fv = rng.standard_normal((500, DIM)).astype(np.float32)
    rows = [(i, sqlite_vec.serialize_float32(orig[i].tolist())) for i in range(5)]
    rows += [(100+i, sqlite_vec.serialize_float32(fv[i].tolist())) for i in range(500)]
    con.executemany("INSERT INTO v(rowid, embedding) VALUES (?, ?)", rows)
    con.commit()
    cps = {}
    n, pc, b = scan(dbpath, fv); cps["BEFORE_delete"] = {"poison_present": n, "posctrl": pc, "bytes": b}
    con.execute("DELETE FROM v WHERE rowid < 5"); con.commit()
    # confirm logical deletion
    logical = con.execute("SELECT count(*) FROM v WHERE rowid < 5").fetchone()[0]
    n, pc, b = scan(dbpath, fv); cps["AFTER_delete"] = {"poison_present": n, "posctrl": pc, "bytes": b, "logical_remaining": logical}
    con.execute("VACUUM"); con.commit()
    n, pc, b = scan(dbpath, fv); cps["AFTER_VACUUM"] = {"poison_present": n, "posctrl": pc, "bytes": b}
    con.close(); os.remove(dbpath)
    return {"seed": seed, "checkpoints": cps}

def summarize(trials):
    def held(t): return all(c["posctrl"] for c in t["checkpoints"].values())
    before = [t["checkpoints"]["BEFORE_delete"]["poison_present"] for t in trials]
    posctrl_ok = all(held(t) for t in trials)
    # DETECTOR-LIMITED case: positive control holds (a live vector IS found, so the scan works),
    # but not all 5 poison are byte-present even BEFORE any delete. That means the engine splits
    # the stored vector across non-contiguous bytes (here: SQLite overflow pages each prefixed
    # with a 4-byte next-page pointer that interrupts the float32 stream). Full-vector byte-exact
    # matching under-counts -> we CANNOT measure deletion durability with this detector. Report
    # honestly as inconclusive; do NOT assign a VEDC class. (SPEC §9 non-contiguous-storage limit.)
    if posctrl_ok and any(b < 5 for b in before):
        return {"engine": "sqlite-vec 0.1.9", "n_trials": len(trials),
                "poison_present_before_delete_per_seed": before, "positive_control_held": posctrl_ok,
                "window_class_observed": "inconclusive (detector-limited)",
                "verdict": ("INCONCLUSIVE — positive control holds but only %s/5 poison are byte-present "
                            "BEFORE any delete: SQLite stores the vector chunk across overflow pages whose "
                            "4-byte page pointers split the contiguous float32 stream, so full-vector "
                            "byte-exact matching under-counts. Needs a SQLite-page-aware (overflow-chain "
                            "reassembling) detector. NOT classified. (SPEC §9)") % before}
    valid = [t for t in trials if t["checkpoints"]["BEFORE_delete"]["poison_present"] == 5 and held(t)]
    after_del = [t["checkpoints"]["AFTER_delete"]["poison_present"] for t in valid]
    after_vac = [t["checkpoints"]["AFTER_VACUUM"]["poison_present"] for t in valid]
    present_after_delete = valid and all(x == 5 for x in after_del)
    purged_by_vacuum = valid and all(x == 0 for x in after_vac)
    if not valid:
        wc, verdict = "inconclusive", "no valid trials (positive control failed)"
    elif present_after_delete and purged_by_vacuum:
        wc = "manual-only"
        verdict = (f"REPLICATED across {len(valid)} seeds: 5/5 present after delete, purged by VACUUM "
                   f"(0/5) in every trial -> VEDC-M, residue survives logical delete until VACUUM rewrites the file")
    elif present_after_delete and not purged_by_vacuum:
        wc, verdict = "unbounded?", f"present after delete and STILL present after VACUUM in some trials: {after_vac}"
    else:
        wc, verdict = "none", f"no residue after delete (after_delete poison={after_del}) — true negative"
    return {"engine": "sqlite-vec 0.1.9", "n_trials": len(trials), "n_valid": len(valid),
            "poison_after_delete_per_valid": after_del, "poison_after_vacuum_per_valid": after_vac,
            "window_class_observed": wc, "verdict": verdict}

def main():
    trials = [run_seed(s) for s in SEEDS]
    for t in trials:
        cp = t["checkpoints"]
        print(f"seed {t['seed']}: before={cp['BEFORE_delete']['poison_present']}/5 "
              f"after_delete={cp['AFTER_delete']['poison_present']}/5 (logical_remaining="
              f"{cp['AFTER_delete']['logical_remaining']}) after_vacuum={cp['AFTER_VACUUM']['poison_present']}/5 "
              f"posctrl={all(c['posctrl'] for c in cp.values())}", flush=True)
    out = {"trials": trials, "summary": summarize(trials)}
    json.dump(out, open(os.path.join(ROOT, "results", "phase23_sqlitevec.json"), "w"), indent=2)
    print("[VERDICT]", out["summary"]["verdict"], flush=True)

if __name__ == "__main__":
    main()
