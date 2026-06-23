# On-disk vector storage layouts (reverse-engineered, for forensic recovery)

Empirically verified during this study (dims cross-checked at 384 and 768). Each entry: how
to find the vectors on disk and how to tell which are deleted. "Blind" = recoverable from raw
files alone (no engine, no IDs).

## ChromaDB (hnswlib HNSW segment) — BLIND, self-identifying
Files: `<persist>/<collection-uuid>/{data_level0.bin, header.bin, length.bin, link_lists.bin}`
plus `<persist>/chroma.sqlite3` (metadata + WAL `embeddings_queue`).

`header.bin` (little-endian; offsets verified on dim 384 & 768):
- `cur_element_count`      @ offset 20 (size_t)
- `size_data_per_element`  @ offset 28 (size_t)   = stride of each element block
- `offsetData`             @ offset 44 (size_t)   = `maxM0*4 + 4` (132 for M=16)
- `dim = (size_data_per_element - offsetData - 8) / 4`   (8 = sizeof label/uint64)

`data_level0.bin` element block i starts at `i * size_data_per_element`:
- bytes [0..2)   : link-list count (uint16)
- byte  [2]      : **`& 0x01` = DELETE_MARK** (set ⇒ logically deleted, still on disk)
- bytes [offsetData .. offsetData+dim*4) : float32[dim] vector (raw, little-endian)
- bytes [offsetData+dim*4 .. +8)         : label (uint64)
Deleted vectors are never reclaimed (no auto-compaction reclaim — phase13/16). Recovery uses
TWO signals with precedence (phase16/17):
- The `DELETE_MARK` bit is only written into the segment AFTER a compaction re-persists it
  (i.e., after enough post-delete writes). In that state, hnswlib labels are reassigned and no
  longer equal sqlite `seq_id`s.
- In the low-post-delete-write state there are ZERO marks, the deletion lives only in
  `chroma.sqlite3`, and segment labels DO equal `seq_id`s. Then: deleted = segment label ∉
  live `seq_id` set, where live = `SELECT seq_id FROM embeddings` for the collection's METADATA
  segment (`segments.scope='METADATA'`). The VECTOR segment dir name == its segment uuid.
Use marks when any mark is present (precise, post-compaction); else use the sqlite-orphan set.
Mixing them (union) double-counts / false-positives — verified, avoided.

## Milvus (segment binlog, parquet) — BLIND, self-identifying
Object store (MinIO/S3) or milvus-lite local dir.
- Segment data: `**/data/*.parquet` (lite) or `**/insert_log/**/*.parquet` (server).
  Columns: `id` (int64 pk), `vector` (list<float>), plus scalar fields. Stores ALL rows
  including deleted ones.
- Delete tombstone: `**/delta/*.parquet` (lite) or `**/delta_log/**` — columns `id`,`_seq`.
- Recover: rows whose `id` ∈ (union of delta `id`s) but still present in the segment parquet.
Persistence bounded by compaction+GC reclaiming superseded segments (often not triggered).

## pgvector / Postgres heap — partially blind
- Vector column is a varlena; for `dim>~500` it is TOASTed: out-of-line in the table's TOAST
  relation (`pg_relation_filepath(reltoastrelid)`), chunked at ~1996 bytes (so match a
  ≤1900-byte prefix of the float32 bytes, not the whole vector). Default storage EXTENDED
  (pglz-compressed); set `STORAGE EXTERNAL` to keep raw.
- Deleted rows are MVCC dead tuples (tuple header `xmax` set) until VACUUM. Plain `VACUUM`
  leaves bytes (reusable, not zeroed); `VACUUM FULL` rewrites and removes them.
- HNSW **index** pages store the vector inline; plain `VACUUM` (ambulkdelete) reclaims them.

## Qdrant (server, Rust) — NOT blind from raw files here
- Local/embedded (Python) mode: single `collection/<name>/storage.sqlite`, points stored as
  **pickled** `PointStruct` (vector + payload) — not raw float32; engine rewrites on close.
- Server mode: immutable segments under mounted storage; vectors are raw float32 (COSINE ⇒
  stored normalized), recoverable by exact byte search if you have the target vector, but the
  raw segment format here was not reverse-engineered enough to enumerate deleted-vs-live blind.
  Vacuum optimizer reclaims deleted vectors.

## Weaviate (Go, LSM + HNSW commitlog) — NOT blind here
- `/var/lib/weaviate/<class>/...`: LSM segment files + `*.hnsw.commitlog.*`. Vectors stored as
  raw float32 (recoverable by exact byte search with the target vector). Deleted objects are
  tombstoned; physical removal awaits async tombstone cleanup / LSM compaction. Blind
  deleted-vs-live enumeration from raw files was not reverse-engineered.

## Scanner notes (lessons learned)
- Exact float32 byte-substring search is alignment-independent and the most reliable detector;
  prefer it over sliding-window cosine when concatenating files of arbitrary length (which
  breaks 4-byte alignment and yields false negatives — see phase9 first run).
- Engines that normalize on insert (COSINE) store normalized vectors — search BOTH raw and
  L2-normalized byte patterns.
- Always run a positive control (a known-present vector must be found) before trusting a null.
