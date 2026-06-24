#!/usr/bin/env python3
"""
Phase 24: SQLite-page-aware residue detector + proper sqlite-vec measurement.

phase23 showed the float32 byte-exact detector under-counts on sqlite-vec because SQLite stores
the vector chunk across OVERFLOW PAGES, each prefixed with a 4-byte big-endian next-page pointer
that interrupts the contiguous float32 stream every page_size bytes.

Fix (principled, not a hack): read the page size from the SQLite header (offset 16, big-endian
uint16; value 1 -> 65536), then build a DE-INTERRUPTED stream = concatenation of each page's
bytes[4:] (dropping the overflow next-page pointer). A vector spanning consecutive overflow
pages becomes contiguous in that stream. We search BOTH the raw file (inline/contiguous vectors)
and the de-interrupted stream (overflow-split vectors); presence = match in either.

This script (a) validates the detector recovers 5/5 BEFORE delete with a positive control, then
(b) measures sqlite-vec deletion durability (before / after delete / after VACUUM) across 3
seeds and prints the VEDC class.
"""
import os, sqlite3, json
import numpy as np
import sqlite_vec
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, ".."))
DIM = 768
orig = np.load(os.path.join(ROOT, "results", "poison_embeddings.npy")).astype(np.float32)
SEEDS = [0, 1, 2]

def sqlite_page_size(raw):
    if len(raw) < 18 or raw[:16] != b"SQLite format 3\x00":
        return None
    ps = int.from_bytes(raw[16:18], "big")
    return 65536 if ps == 1 else ps

def deinterrupt(raw, ps):
    """Drop the first 4 bytes (overflow next-page pointer) of every page and concatenate the
    remainder, so data spread across an overflow chain becomes contiguous."""
    out = bytearray()
    for off in range(0, len(raw) - (len(raw) % ps if ps else 0), ps):
        out += raw[off + 4: off + ps]
    return bytes(out)

def detect(raw, vecs):
    """Return how many of `vecs` are byte-present, searching raw + de-interrupted (raw OR norm)."""
    ps = sqlite_page_size(raw)
    streams = [raw]
    if ps:
        streams.append(deinterrupt(raw, ps))
    def present(v):
        nb = v.astype(np.float32).tobytes(); vn = (v / np.linalg.norm(v)).astype(np.float32).tobytes()
        return any(nb in s or vn in s for s in streams)
    return [present(v) for v in vecs]

def detect_raw_only(raw, vecs):
    def present(v):
        nb = v.astype(np.float32).tobytes(); vn = (v / np.linalg.norm(v)).astype(np.float32).tobytes()
        return nb in raw or vn in raw
    return [present(v) for v in vecs]

def run_seed(seed):
    dbpath = os.path.join(ROOT, "db", f"_sqlitedet_seed{seed}.db")
    if os.path.exists(dbpath): os.remove(dbpath)
    con = sqlite3.connect(dbpath); con.enable_load_extension(True); sqlite_vec.load(con); con.enable_load_extension(False)
    con.execute(f"CREATE VIRTUAL TABLE v USING vec0(embedding float[{DIM}])")
    rng = np.random.default_rng(seed); fv = rng.standard_normal((500, DIM)).astype(np.float32)
    rows = [(i, sqlite_vec.serialize_float32(orig[i].tolist())) for i in range(5)]
    rows += [(100 + i, sqlite_vec.serialize_float32(fv[i].tolist())) for i in range(500)]
    con.executemany("INSERT INTO v(rowid, embedding) VALUES (?, ?)", rows); con.commit()

    def checkpoint():
        raw = open(dbpath, "rb").read()
        poison_aware = detect(raw, [orig[k] for k in range(5)])
        poison_raw = detect_raw_only(raw, [orig[k] for k in range(5)])
        posctrl = detect(raw, [fv[0]])[0]
        return {"poison_aware": sum(poison_aware), "poison_raw_only": sum(poison_raw),
                "posctrl_aware": bool(posctrl), "bytes": len(raw)}

    cps = {"BEFORE_delete": checkpoint()}
    con.execute("DELETE FROM v WHERE rowid < 5"); con.commit()
    logical = con.execute("SELECT count(*) FROM v WHERE rowid < 5").fetchone()[0]
    cps["AFTER_delete"] = {**checkpoint(), "logical_remaining": logical}
    con.execute("VACUUM"); con.commit()
    cps["AFTER_VACUUM"] = checkpoint()
    con.close(); os.remove(dbpath)
    return {"seed": seed, "checkpoints": cps}

def summarize(trials):
    def held(t): return all(c["posctrl_aware"] for c in t["checkpoints"].values())
    valid = [t for t in trials if t["checkpoints"]["BEFORE_delete"]["poison_aware"] == 5 and held(t)]
    after_del = [t["checkpoints"]["AFTER_delete"]["poison_aware"] for t in valid]
    after_vac = [t["checkpoints"]["AFTER_VACUUM"]["poison_aware"] for t in valid]
    detector_gain = {t["seed"]: {"raw_only_before": t["checkpoints"]["BEFORE_delete"]["poison_raw_only"],
                                 "page_aware_before": t["checkpoints"]["BEFORE_delete"]["poison_aware"]}
                     for t in trials}
    if not valid:
        return {"engine": "sqlite-vec 0.1.9", "n_valid": 0, "detector_gain": detector_gain,
                "verdict": "page-aware detector still did not recover 5/5 before delete; see counts"}
    present_after_delete = all(x == 5 for x in after_del)
    no_residue_after_delete = all(x == 0 for x in after_del)
    purged_by_vacuum = all(x == 0 for x in after_vac)
    gain = detector_gain[valid[0]['seed']]
    fixed = f"detector FIXED before-delete (raw-only {gain['raw_only_before']}/5 -> page-aware {gain['page_aware_before']}/5)"
    if no_residue_after_delete:
        wc = "none"; v = (f"{fixed}. REPLICATED across {len(valid)} seeds: 5/5 present before delete, "
                          f"0/5 after a committed delete (positive control still found) -> NO recoverable "
                          f"residue. vec0 compacts/rewrites its vector chunk on delete -> VEDC-N (good privacy).")
    elif present_after_delete and purged_by_vacuum:
        wc = "manual-only"; v = f"{fixed}. residue present after delete (5/5), purged by VACUUM (0/5) -> VEDC-M"
    elif present_after_delete and not purged_by_vacuum:
        wc = "unbounded"; v = f"{fixed}. present after delete AND after VACUUM: {after_vac}"
    else:
        wc = "partial"; v = f"{fixed}. after_delete poison counts {after_del} (mixed) — investigate"
    return {"engine": "sqlite-vec 0.1.9", "n_valid": len(valid), "detector_gain": detector_gain,
            "poison_after_delete_per_valid": after_del, "poison_after_vacuum_per_valid": after_vac,
            "window_class_observed": wc, "verdict": v}

def main():
    trials = [run_seed(s) for s in SEEDS]
    for t in trials:
        cp = t["checkpoints"]
        print(f"seed {t['seed']}: before raw={cp['BEFORE_delete']['poison_raw_only']}/5 "
              f"page-aware={cp['BEFORE_delete']['poison_aware']}/5 (posctrl {cp['BEFORE_delete']['posctrl_aware']}) | "
              f"after_delete={cp['AFTER_delete']['poison_aware']}/5 (logical_remaining "
              f"{cp['AFTER_delete']['logical_remaining']}) | after_vacuum={cp['AFTER_VACUUM']['poison_aware']}/5", flush=True)
    out = {"trials": trials, "summary": summarize(trials)}
    json.dump(out, open(os.path.join(ROOT, "results", "phase24_sqlite_detector.json"), "w"), indent=2)
    print("[VERDICT]", out["summary"]["verdict"], flush=True)

if __name__ == "__main__":
    main()
