#!/usr/bin/env python3
"""
vecdb_residue_audit.py -- deletion-effectiveness auditor for ChromaDB.

Defensive use: after you delete records (e.g. an erasure / right-to-be-forgotten
request), verify the embedding vectors are actually gone from disk. This reads the
raw hnswlib HNSW segment(s) and reports vectors that are logically deleted
(DELETE_MARK bit set) but still physically present and recoverable.

It does NOT need the embedding model or any vector DB process -- pure file forensics.

Usage:
  vecdb_residue_audit.py <chroma_persist_dir> [--dump out.npy]

Exit code 2 if any recoverable deleted residue is found (so it can gate CI/erasure
verification), 0 if clean.
"""
import sys, os, glob, struct, json
import numpy as np

DELETE_MARK = 0x01  # hnswlib: byte at element_offset+2, bit0

def infer_dim_from_sqlite(persist_dir):
    """best-effort: read configured dimension if present, else None."""
    import sqlite3
    f = os.path.join(persist_dir, "chroma.sqlite3")
    if not os.path.isfile(f): return None
    try:
        con = sqlite3.connect(f)
        # collection metadata may store dimension; fall back to None
        for tbl in ["collections", "segment_metadata", "embedding_metadata"]:
            try:
                rows = con.execute(f"SELECT * FROM {tbl}").fetchall()
            except Exception:
                pass
        con.close()
    except Exception:
        pass
    return None

def dims_from_header(segfile, label=8):
    """Robust: parse sibling hnswlib header.bin (writeBinaryPOD order) for exact
    size_data_per_element_ and offsetData_. Returns (dim, stride, off_data, n_hdr)."""
    hdr = os.path.join(os.path.dirname(segfile), "header.bin")
    if not os.path.isfile(hdr):
        return None
    b = open(hdr, "rb").read()
    if len(b) < 52:
        return None
    # empirically verified field offsets in Chroma's hnswlib header.bin (little-endian
    # size_t): cur_element_count@20, size_data_per_element@28, offsetData@44.
    # Cross-checked on dim=384 and dim=768 segments.
    cur_count = struct.unpack_from("<Q", b, 20)[0]
    size_data_per_element = struct.unpack_from("<Q", b, 28)[0]
    offsetData = struct.unpack_from("<Q", b, 44)[0]
    dim = (size_data_per_element - offsetData - label) // 4
    # sanity (NON-tautological): offsetData must equal hnswlib links block maxM0*4+4
    # for some plausible maxM0, and dim must be a sane embedding size.
    if not (0 < dim <= 8192): return None
    if (offsetData + dim*4 + label) != size_data_per_element: return None
    if (offsetData - 4) % 4 != 0: return None
    return dim, size_data_per_element, offsetData, cur_count

def infer_dim(segfile, maxM0=32, label=8):
    """fallback: recover DIM from file size assuming uniform stride."""
    size = os.path.getsize(segfile); links = maxM0*4 + 4
    for dim in range(16, 4097):
        stride = links + dim*4 + label
        if size % stride == 0:
            return dim, stride, links
    return None, None, None

def audit_segment(segfile):
    hdr = dims_from_header(segfile)
    if hdr:
        dim, stride, off_data, n_hdr = hdr
    else:
        dim, stride, off_data = infer_dim(segfile)
        n_hdr = None
    if dim is None:
        return {"segment": segfile, "error": "could not determine stride/dim"}
    data = open(segfile, "rb").read()
    n = len(data)//stride
    deleted = []
    for i in range(n):
        base = i*stride
        if data[base+2] & DELETE_MARK:
            v = np.frombuffer(data[base+off_data:base+off_data+dim*4], dtype=np.float32).copy()
            label = struct.unpack_from("<Q", data, base+off_data+dim*4)[0]
            deleted.append((i, label, v))
    return {"segment": segfile, "dim": dim, "stride": stride, "total_elements": n,
            "dim_source": "header.bin" if hdr else "size-inference",
            "cur_count_header": n_hdr,
            "deleted_recoverable": len(deleted),
            "deleted_labels": [d[1] for d in deleted], "_vecs": [d[2] for d in deleted]}

def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    persist = sys.argv[1]
    dump = None
    if "--dump" in sys.argv:
        dump = sys.argv[sys.argv.index("--dump")+1]
    segs = glob.glob(os.path.join(persist, "**", "data_level0.bin"), recursive=True)
    if not segs:
        print(f"[!] no HNSW segments under {persist}"); sys.exit(1)
    report = {"persist_dir": persist, "segments": [], "total_deleted_recoverable": 0}
    allvecs = []
    for s in segs:
        r = audit_segment(s)
        allvecs += r.pop("_vecs", [])
        report["segments"].append(r)
        report["total_deleted_recoverable"] += r.get("deleted_recoverable", 0)
    print(json.dumps(report, indent=2))
    if dump and allvecs:
        np.save(dump, np.stack(allvecs)); print(f"[*] dumped {len(allvecs)} recovered vectors -> {dump}")
    n = report["total_deleted_recoverable"]
    print(f"\n{'[FAIL] ' if n else '[OK] '}{n} logically-deleted vector(s) still recoverable on disk.")
    sys.exit(2 if n else 0)

if __name__ == "__main__":
    main()
