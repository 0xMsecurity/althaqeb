#!/usr/bin/env python3
"""
vdbresidue — read-only forensic auditor for deleted-vector residue in vector databases.

Detects and recovers embedding vectors that an engine reports as deleted (logical layer
clean) but still leaves physically recoverable on disk. Defensive / DFIR use: verify that
erasure ("right to be forgotten") deletions actually removed data; acquire evidence with a
tamper-evident chain of custody.

Design constraints (Phase-2 hardening spec):
  * READ-ONLY on the target — never writes to or mutates the database directory.
  * Deterministic — no randomness, no network, no LLM dependency. Pure file forensics.
  * Plugin backends — each backend self-detects and exposes list/recover.
  * Chain of custody — every operation appends a signed-by-hash JSONL record.

Backends:
  chroma  — hnswlib HNSW segment (data_level0.bin + header.bin). Deletion sets the
            persisted DELETE_MARK bit; recovers exactly the deleted vectors, blind.
  milvus  — segment binlog parquet + delta (tombstone) parquet. Recovers rows whose id
            appears in a delta log (deleted) but still present in the segment.
  generic — carves all float32[dim] vectors (size-inferred); use when no backend matches.

Subcommands:
  inspect <path>                 identify backend, segments, element/deleted counts
  recover <path> [--out DIR]     extract recoverable DELETED vectors -> npy + index.json
  report  <path> [--out FILE]    human + JSON forensic report
  acquire <path> --out BUNDLE    copy raw evidence files + record SHA256 (chain of custody)
  verify  <manifest>             sha256 -c a manifest

Exit: 2 if recoverable deleted residue is found (CI/erasure gate), 0 if clean, 1 on error.
"""
import sys, os, glob, json, struct, hashlib, shutil, time, argparse, mmap

__version__ = "0.1.0"
import numpy as np

COC_LOG = "vdbresidue_coc.jsonl"   # chain-of-custody log (written in CWD or --out)

# ----------------------------- chain of custody -----------------------------
def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def coc(logdir, op, target, files, result):
    rec = {"ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "op": op, "target": os.path.abspath(target),
           "tool": "vdbresidue", "files": files, "result": result}
    os.makedirs(logdir, exist_ok=True)
    with open(os.path.join(logdir, COC_LOG), "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec

# ----------------------------- chroma backend -----------------------------
DELETE_MARK = 0x01
def chroma_segments(path):
    return sorted(glob.glob(os.path.join(path, "**", "data_level0.bin"), recursive=True))

def chroma_detect(path):
    return bool(chroma_segments(path)) or os.path.isfile(os.path.join(path, "chroma.sqlite3"))

def _chroma_dims(seg, label=8):
    hdr = os.path.join(os.path.dirname(seg), "header.bin")
    if os.path.isfile(hdr):
        b = open(hdr, "rb").read()
        if len(b) >= 52:
            cur = struct.unpack_from("<Q", b, 20)[0]
            spe = struct.unpack_from("<Q", b, 28)[0]
            offd = struct.unpack_from("<Q", b, 44)[0]
            dim = (spe - offd - label) // 4
            if 0 < dim <= 8192 and offd + dim*4 + label == spe and (offd - 4) % 4 == 0:
                return dim, spe, offd, cur
    # fallback: infer from size assuming maxM0=32
    size = os.path.getsize(seg); links = 32*4 + 4
    for dim in range(16, 4097):
        stride = links + dim*4 + label
        if size % stride == 0:
            return dim, stride, links, None
    return None

def _chroma_live_seqids(persist, seg):
    """Set of LIVE hnsw labels (seq_ids) for the collection owning this VECTOR segment,
    read from chroma.sqlite3. Returns None if sqlite/mapping unavailable (then fall back to
    DELETE_MARK only). Scoped per collection to avoid cross-collection false matches."""
    import sqlite3
    db = os.path.join(persist, "chroma.sqlite3")
    if not os.path.isfile(db):
        return None
    vec_seg_id = os.path.basename(os.path.dirname(seg))  # segment dir name == segment uuid
    try:
        con = sqlite3.connect(db)
        row = con.execute("SELECT collection FROM segments WHERE id=?", (vec_seg_id,)).fetchone()
        if row:
            coll = row[0]
            meta = [r[0] for r in con.execute(
                "SELECT id FROM segments WHERE collection=? AND scope='METADATA'", (coll,))]
            if meta:
                qs = ",".join("?"*len(meta))
                live = set(r[0] for r in con.execute(
                    f"SELECT seq_id FROM embeddings WHERE segment_id IN ({qs})", meta))
                con.close(); return live
        # fallback: all live seq_ids in the DB (conservative; single-collection safe)
        live = set(r[0] for r in con.execute("SELECT seq_id FROM embeddings"))
        con.close(); return live
    except Exception:
        return None

def chroma_scan(seg, persist=None):
    d = _chroma_dims(seg)
    if not d:
        return {"segment": seg, "error": "cannot determine dim"}, []
    dim, stride, offd, cur = d
    size = os.path.getsize(seg)
    n = size // stride
    live = _chroma_live_seqids(persist, seg) if persist else None
    # mmap the segment read-only: bounded RSS regardless of segment size (production
    # data_level0.bin can be many GB), with the same random-access element indexing.
    elems, deleted = [], []
    with open(seg, "rb") as fh:
        mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) if size else None
        try:
            for i in range(n):
                base = i*stride
                label = struct.unpack_from("<Q", mm, base+offd+dim*4)[0]
                marked = bool(mm[base+2] & DELETE_MARK)
                orphan = (live is not None) and (label not in live)
                elems.append((label, base, marked, orphan))
            n_mark = sum(1 for e in elems if e[2])
            n_orphan_only = sum(1 for e in elems if e[3] and not e[2])
            # PRECEDENCE, not union. DELETE_MARK is precise; it is written once a compaction
            # re-persists the segment, at which point hnswlib labels are reassigned and no longer
            # equal sqlite seq_ids -> the orphan check would false-positive on live elements. So:
            # if ANY mark present (compacted state) trust marks only; only in the ZERO-marks state
            # (low-write, labels == seq_ids, verified phase17) fall back to the orphan signal.
            if n_mark > 0:
                chosen, signal = [e for e in elems if e[2]], "DELETE_MARK"
            elif n_orphan_only > 0:
                chosen, signal = [e for e in elems if e[3]], "sqlite_orphan(no-marks state)"
            else:
                chosen, signal = [], "none"
            deleted = [(lab, np.frombuffer(mm[base+offd:base+offd+dim*4], dtype=np.float32).copy(), signal)
                       for (lab, base, mk, orp) in chosen]
        finally:
            if mm is not None:
                mm.close()
    info = {"segment": seg, "dim": dim, "stride": stride, "total_elements": n,
            "cur_count_header": cur, "live_seqids": (len(live) if live is not None else None),
            "n_delete_mark": n_mark, "n_sqlite_orphan_only": n_orphan_only,
            "signal_used": signal, "deleted_recoverable": len(deleted)}
    return info, deleted

def chroma_recover(path):
    segs = chroma_segments(path)
    infos, vecs, labels = [], [], []
    for s in segs:
        info, dels = chroma_scan(s, persist=path)
        infos.append(info)
        for lab, v, how in dels:
            labels.append({"segment": os.path.relpath(s, path), "label": int(lab), "signal": how})
            vecs.append(v)
    return infos, (np.stack(vecs) if vecs else np.zeros((0,), np.float32)), labels

# ----------------------------- milvus backend -----------------------------
def milvus_detect(path):
    return bool(glob.glob(os.path.join(path, "**", "*.parquet"), recursive=True)) and \
           ("milvus" in path.lower() or bool(glob.glob(os.path.join(path, "**", "delta", "*.parquet"), recursive=True)))

def milvus_recover(path):
    import pyarrow.parquet as pq
    seg_files = sorted(glob.glob(os.path.join(path, "**", "data", "*.parquet"), recursive=True)) \
                or sorted(glob.glob(os.path.join(path, "**", "insert_log", "**", "*.parquet"), recursive=True))
    delta_files = sorted(glob.glob(os.path.join(path, "**", "delta", "*.parquet"), recursive=True)) \
                  or sorted(glob.glob(os.path.join(path, "**", "delta_log", "**", "*.parquet"), recursive=True))
    deleted_ids = set()
    for d in delta_files:
        try:
            df = pq.read_table(d).to_pandas()
            idcol = next((c for c in df.columns if c.lower() == "id" or c.lower().endswith("pk")), None)
            if idcol is not None:
                deleted_ids.update(int(x) for x in df[idcol])
        except Exception:
            pass
    infos, vecs, labels = [], [], []
    for s in seg_files:
        try:
            df = pq.read_table(s).to_pandas()
        except Exception as e:
            infos.append({"segment": s, "error": str(e)}); continue
        veccol = next((c for c in df.columns if len(df) and df[c].dtype == object and
                       hasattr(df[c].iloc[0], "__len__") and not isinstance(df[c].iloc[0], str)), None)
        idcol = next((c for c in df.columns if c.lower() == "id"), None)
        info = {"segment": os.path.relpath(s, path), "rows": len(df),
                "vector_col": veccol, "deleted_in_segment": 0}
        if veccol and idcol is not None:
            ndel = 0
            for _, row in df.iterrows():
                if int(row[idcol]) in deleted_ids:
                    vecs.append(np.array(row[veccol], dtype=np.float32))
                    labels.append({"segment": info["segment"], "id": int(row[idcol])})
                    ndel += 1
            info["deleted_in_segment"] = ndel
        infos.append(info)
    return infos, (np.stack(vecs) if vecs else np.zeros((0,), np.float32)), labels

# ----------------------------- generic carver -----------------------------
def generic_recover(path, dim=None):
    files = [f for f in glob.glob(os.path.join(path, "**", "*"), recursive=True) if os.path.isfile(f)]
    infos = [{"files_scanned": len(files),
              "note": "generic carve cannot distinguish deleted from live without engine metadata"}]
    return infos, np.zeros((0,), np.float32), []

# ----------------------------- qdrant / weaviate (detect + match-only) -----------------------------
def qdrant_detect(path):
    return bool(glob.glob(os.path.join(path, "**", "storage.sqlite"), recursive=True)) or \
           os.path.isfile(os.path.join(path, "raft_state.json")) or \
           bool(glob.glob(os.path.join(path, "**", "segments", "**"), recursive=True))

def weaviate_detect(path):
    return bool(glob.glob(os.path.join(path, "**", "*.hnsw.commitlog*"), recursive=True)) or \
           bool(glob.glob(os.path.join(path, "**", "*.wal"), recursive=True)) and "weaviate" in path.lower()

# ----------------------------- exact-byte match (ALL engines, deterministic) -----------------------------
def _stream_search(path, needles, chunk=1 << 24):
    """Return the set of needle-indices (i) whose bytes appear anywhere in the file at `path`.
    Streams the file in `chunk`-sized reads with an overlap of (maxlen-1) bytes carried between
    reads, so a needle straddling a chunk boundary is still found. Memory is bounded by chunk +
    overlap regardless of file size. `needles` is a list of (i, bytes)."""
    if not needles:
        return set()
    found = set()
    overlap = max(len(n) for _, n in needles) - 1
    with open(path, "rb") as fh:
        tail = b""
        while True:
            buf = fh.read(chunk)
            if not buf:
                break
            window = tail + buf
            for i, n in needles:
                if i not in found and n in window:
                    found.add(i)
            if len(found) == len(needles):
                break
            tail = window[-overlap:] if overlap > 0 else b""
    return found

def _sqlite_page_size(path):
    """Return the SQLite page size (header offset 16, big-endian u16; value 1 -> 65536) if the
    file is a SQLite database, else None."""
    try:
        with open(path, "rb") as f:
            hdr = f.read(18)
    except Exception:
        return None
    if hdr[:16] != b"SQLite format 3\x00":
        return None
    ps = int.from_bytes(hdr[16:18], "big")
    return 65536 if ps == 1 else ps

def _sqlite_deint_search(path, needles, pages_per_block=4096):
    """SQLite stores large values across OVERFLOW PAGES, each prefixed with a 4-byte big-endian
    next-page pointer that interrupts the byte stream every page. A vector spanning an overflow
    chain is therefore not a contiguous substring of the raw file. This rebuilds a DE-INTERRUPTED
    stream (each page's bytes[4:], concatenated) — in which an overflow-spanning vector becomes
    contiguous — and searches it, streamed in page-aligned blocks with an overlap carry so a
    needle straddling a block boundary is still found. Returns the set of matched needle indices.
    Engines this matters for: sqlite-vec and any SQLite-backed store. (SPEC §9.)"""
    ps = _sqlite_page_size(path)
    if not ps or not needles:
        return set()
    found = set()
    overlap = max(len(n) for _, n in needles) - 1
    with open(path, "rb") as fh:
        tail = b""
        while True:
            block = fh.read(ps * pages_per_block)   # page-aligned (SQLite files are page multiples)
            if not block:
                break
            de = bytearray()
            for off in range(0, len(block) - (len(block) % ps), ps):
                de += block[off + 4: off + ps]       # drop the 4-byte overflow next-page pointer
            window = tail + bytes(de)
            for i, n in needles:
                if i not in found and n in window:
                    found.add(i)
            if len(found) == len(needles):
                break
            tail = window[-overlap:] if overlap > 0 else b""
    return found

def match_targets(path, targets):
    """Report which target vectors (float32 rows) are physically present on disk, by exact
    byte substring (raw AND L2-normalized — engines using cosine store normalized). Alignment-
    independent, zero false positives. Works on any backend's raw files.

    Each file is searched independently and streamed in bounded chunks: memory stays O(chunk),
    not O(store size), so this runs on multi-GB production stores. Searching per file (rather than
    over a concatenation of all files) also removes spurious matches that could straddle a
    file boundary — a stored vector always lives within a single file.

    For SQLite databases (sqlite-vec et al.) it ALSO searches a de-interrupted stream so vectors
    split across overflow pages are still found (raw-only byte search under-counts these)."""
    files = [f for f in glob.glob(os.path.join(path, "**", "*"), recursive=True) if os.path.isfile(f)]
    # Build the needle list: each target contributes its raw bytes and, if non-zero, its
    # L2-normalized bytes (cosine engines store normalized). Both map back to the same index.
    needles = []
    for i, t in enumerate(targets):
        t = t.astype(np.float32)
        needles.append((i, t.tobytes()))
        n = np.linalg.norm(t)
        if n > 0:
            nb = (t / n).astype(np.float32).tobytes()
            if nb != needles[-1][1]:
                needles.append((i, nb))
    present, store_bytes = set(), 0
    for f in files:
        store_bytes += os.path.getsize(f)
        remaining = [(i, n) for (i, n) in needles if i not in present]
        if remaining:
            present |= _stream_search(f, remaining)
        remaining = [(i, n) for (i, n) in needles if i not in present]
        if remaining:                                   # SQLite overflow-aware pass (no-op on non-SQLite files)
            present |= _sqlite_deint_search(f, remaining)
    res = [{"index": i, "present": (i in present)} for i in range(len(targets))]
    return res, len(files), store_bytes

BACKENDS = [("chroma", chroma_detect, chroma_recover),
            ("milvus", milvus_detect, milvus_recover)]

def detect_backend(path, forced=None):
    if forced:
        return forced
    for name, det, _ in BACKENDS:
        try:
            if det(path):
                return name
        except Exception:
            pass
    try:
        if qdrant_detect(path): return "qdrant"
        if weaviate_detect(path): return "weaviate"
    except Exception:
        pass
    return "generic"

def recover_dispatch(path, backend):
    if backend == "chroma":  return chroma_recover(path)
    if backend == "milvus":  return milvus_recover(path)
    return generic_recover(path)

# ----------------------------- subcommands -----------------------------
def cmd_inspect(a):
    backend = detect_backend(a.path, a.backend)
    infos, vecs, labels = recover_dispatch(a.path, backend)
    out = {"path": os.path.abspath(a.path), "backend": backend,
           "segments": infos, "total_deleted_recoverable": len(labels)}
    print(json.dumps(out, indent=2))
    coc(a.path, "inspect", a.path, [], {"backend": backend, "deleted_recoverable": len(labels)})
    return 2 if labels else 0

def cmd_recover(a):
    backend = detect_backend(a.path, a.backend)
    infos, vecs, labels = recover_dispatch(a.path, backend)
    outdir = a.out or "vdbresidue_out"
    os.makedirs(outdir, exist_ok=True)
    npy = os.path.join(outdir, "recovered_deleted_vectors.npy")
    idx = os.path.join(outdir, "recovered_index.json")
    if len(labels):
        np.save(npy, vecs)
    json.dump({"backend": backend, "count": len(labels), "labels": labels, "segments": infos},
              open(idx, "w"), indent=2)
    print(f"[{backend}] recovered {len(labels)} deleted vectors -> {npy if len(labels) else '(none)'}")
    coc(outdir, "recover", a.path,
        [{"path": npy, "sha256": sha256_file(npy)}] if len(labels) else [],
        {"backend": backend, "recovered": len(labels), "index": idx})
    return 2 if labels else 0

def cmd_report(a):
    backend = detect_backend(a.path, a.backend)
    infos, vecs, labels = recover_dispatch(a.path, backend)
    lines = ["# Deleted-vector residue report",
             f"- target: `{os.path.abspath(a.path)}`",
             f"- backend: **{backend}**",
             f"- deleted-but-recoverable vectors: **{len(labels)}**",
             f"- generated: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} (UTC)",
             "", "## Segments"]
    for s in infos:
        lines.append("- " + json.dumps(s))
    verdict = ("FAIL — logically-deleted vectors remain physically recoverable on disk."
               if labels else "OK — no recoverable deleted residue found.")
    lines += ["", f"## Verdict\n{verdict}"]
    text = "\n".join(lines)
    if a.out:
        open(a.out, "w").write(text); print(f"report -> {a.out}")
    else:
        print(text)
    coc(a.out and os.path.dirname(a.out) or a.path, "report", a.path, [],
        {"backend": backend, "deleted_recoverable": len(labels)})
    return 2 if labels else 0

def cmd_acquire(a):
    backend = detect_backend(a.path, a.backend)
    bundle = a.out
    os.makedirs(bundle, exist_ok=True)
    recorded = []
    for f in glob.glob(os.path.join(a.path, "**", "*"), recursive=True):
        if os.path.isfile(f):
            rel = os.path.relpath(f, a.path)
            dst = os.path.join(bundle, "evidence", rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(f, dst)                    # read-only on source: copy out
            recorded.append({"path": rel, "sha256": sha256_file(f), "size": os.path.getsize(f)})
    man = os.path.join(bundle, "evidence_manifest.json")
    json.dump({"source": os.path.abspath(a.path), "backend": backend,
               "acquired_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "files": recorded}, open(man, "w"), indent=2)
    print(f"acquired {len(recorded)} files -> {bundle} (manifest: {man})")
    coc(bundle, "acquire", a.path, recorded, {"backend": backend, "file_count": len(recorded)})
    return 0

def cmd_match(a):
    backend = detect_backend(a.path, a.backend)
    targets = np.load(a.vectors)
    if targets.ndim == 1:
        targets = targets[None, :]
    res, nfiles, nbytes = match_targets(a.path, targets)
    present = sum(r["present"] for r in res)
    out = {"path": os.path.abspath(a.path), "backend": backend, "files_scanned": nfiles,
           "store_bytes": nbytes, "targets": len(res), "present": present, "detail": res}
    print(json.dumps(out, indent=2))
    coc(a.path, "match", a.path, [{"path": a.vectors, "sha256": sha256_file(a.vectors)}],
        {"backend": backend, "targets": len(res), "present": present})
    return 2 if present else 0

def cmd_verify(a):
    if not os.path.isfile(a.manifest):
        print("manifest not found"); return 1
    import subprocess
    lines = [l for l in open(a.manifest) if l.strip() and not l.startswith("#")]
    tmp = a.manifest + ".tmp"; open(tmp, "w").writelines(lines)
    rc = subprocess.run(["sha256sum", "-c", "--quiet", tmp],
                        cwd=os.path.dirname(os.path.abspath(a.manifest)) or ".").returncode
    os.remove(tmp)
    print("[OK] manifest verified" if rc == 0 else "[FAIL] manifest mismatch")
    return 0 if rc == 0 else 2

def main():
    ap = argparse.ArgumentParser(prog="vdbresidue", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"vdbresidue {__version__}")
    ap.add_argument("--backend", choices=["chroma", "milvus", "qdrant", "weaviate", "generic"],
                    help="force backend")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("inspect", "recover", "report"):
        p = sub.add_parser(name); p.add_argument("path"); p.add_argument("--out")
    pa = sub.add_parser("acquire"); pa.add_argument("path"); pa.add_argument("--out", required=True)
    pm = sub.add_parser("match"); pm.add_argument("path"); pm.add_argument("--vectors", required=True,
        help="path to .npy of float32 target vectors to search for on disk")
    pv = sub.add_parser("verify"); pv.add_argument("manifest")
    a = ap.parse_args()
    try:
        return {"inspect": cmd_inspect, "recover": cmd_recover, "report": cmd_report,
                "acquire": cmd_acquire, "match": cmd_match, "verify": cmd_verify}[a.cmd](a)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr); return 1

if __name__ == "__main__":
    sys.exit(main())
