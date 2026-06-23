# Disclosure drafts — STATUS: NOT SENT (awaiting human approval)

These are **drafts**. Nothing here has been transmitted to any vendor. Sending a
disclosure is an ethical/coordination decision reserved for the human operator
(see the project's interruption policy). Do not send without explicit approval.

## Honest framing (read before sending anything)
This is a **data-lifecycle / "deletion ≠ secure erasure"** finding, not a memory-safety or
RCE vulnerability. Logical deletion leaves the embedding vector physically recoverable on
disk until (if ever) a compaction/vacuum reclaims the space. This behavior is partly
*expected* for LSM/segment storage engines and is in the same family as Stahlberg et al.,
SIGMOD 2007 ("forensic analysis of database tampering" / deleted-record persistence).

What is **novel and worth reporting**:
1. The residue is an **embedding vector that is invertible to its source text** (vec2text),
   so "opaque floats on disk" are recoverable content — relevant to GDPR/CCPA erasure.
2. In some engines the deletion is **self-identifying** (Chroma `DELETE_MARK`, Milvus delta
   tombstone), enabling **selective blind recovery of exactly the erased records**.
3. In ChromaDB the residue is **unbounded** (no observed reclamation across 50k writes,
   restarts, collection-drop).

## Severity stance (no exaggeration, no CVE/legal claims)
- Requires **filesystem/backup/host access** to the persistence directory (not a remote bug).
- Severity is a **privacy/compliance** concern (erasure ineffectiveness), typically Low–Medium
  depending on deployment (e.g. shared storage, snapshots, decommissioned disks, multi-tenant).
- Per-engine durability differs sharply — state it accurately per report.

## Per-vendor drafts
| Draft | Engine | Durability observed | Suggested ask |
|---|---|---|---|
| `chroma.md`   | ChromaDB | unbounded (no auto-purge) | document + optional secure-delete / compaction-on-delete / zeroing |
| `milvus.md`   | Milvus | persists until compaction+GC reclaim (often not for small deletes) | document erasure semantics; guidance on forcing compaction+GC |
| `weaviate.md` | Weaviate | persisted ≥ tested window (async tombstone cleanup) | document cleanup timing; erasure guidance |
| `qdrant_pgvector_fyi.md` | Qdrant / pgvector | residue present post-delete; purged by optimizer/VACUUM | FYI / docs note (lower severity) |

## Coordinated-disclosure defaults (fill in before sending)
- Channel: each project's SECURITY.md / security@ / private GitHub advisory.
- Timeline: 90 days standard; offer to extend; no public PoC of inversion before fix/agreement.
- Provide: versions, environment, `../REPRODUCE.md`, relevant `../results/*.json`, mitigations.
- Tone: collaborative, factual; this is hardening guidance, not an accusation.
