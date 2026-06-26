# Disclosure drafts — STATUS: STAGED / READY, NOT SENT (awaiting human approval)

These are **staged advisories**. Nothing here has been transmitted to any vendor. Sending a
disclosure is an ethical/coordination decision reserved for the human operator (project human
gate). **The agent prepares, classifies, and stages; a human sends.** Do not send without
explicit human approval.

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
   tombstone, Postgres `xmax`), enabling **selective blind recovery of exactly the erased records**.
3. In ChromaDB the residue is **unbounded** (no observed reclamation across 50k writes,
   restarts, collection-drop, idle, four reclaim attacks, 60% high-ratio delete) — the unique
   `VEDC-U` class.

Each advisory now carries its **VEDC class** from the committed standard
(`../../../standards/erasure-durability/`, roster in `CLASSIFICATION.md`). The class is the
honest, evidence-gated severity anchor — it replaces ad-hoc adjectives.

## Severity stance (no exaggeration, no CVE/legal claims)
- Requires **filesystem/backup/host/object-store access** to the persistence data (not a remote bug).
- Severity is a **privacy/compliance** concern (erasure ineffectiveness), typically Low–Medium
  depending on deployment (shared storage, snapshots, decommissioned disks, multi-tenant).
- Per-engine durability differs sharply — the VEDC class states it accurately per report.
- **Frame decided by tournament (`../../../GRAVEYARD.md`):** the privacy/compliance-defect frame
  won; the CVE/"critical-vulnerability" escalation frame was killed (requires filesystem access;
  any CVSS we have not computed would be an asserted number; vendors rightly dispute
  "vulnerability" for expected LSM behavior). Self-cleaning engines are FYI/docs-tier.

## Dual-use → defensive
The defensive deliverable is `../tool/vdbresidue.py` — a read-only erasure-verification auditor
an operator runs to **prove** a right-to-erasure deletion actually removed the bytes (or to find
that it did not). The advisories give defensive uplift (how to verify and force physical
reclamation) without a weaponization recipe; no public PoC of inversion before fix/agreement.

## Per-vendor advisories — VEDC class + observed durability
| Advisory | Engine | VEDC class | Conformance | Suggested ask |
|---|---|---|---|---|
| `chroma.md`   | ChromaDB | **VEDC-U+S** (unbounded) | Confirmed | document + optional secure-delete / compaction-on-delete / zeroing |
| `milvus.md`   | Milvus | VEDC-AT+S (compaction+GC timer) | Provisional | document erasure semantics; guidance on forcing compaction+GC |
| `weaviate.md` | Weaviate | VEDC-AT (tombstone-cleanup timer) | Confirmed | document cleanup timing; erasure guidance |
| `qdrant_pgvector_fyi.md` | Qdrant / pgvector | VEDC-AU / AU+M+S | Confirmed | FYI / docs note (lower severity — routine maintenance reclaims) |

## Disclosure status tracker — lifecycle: DRAFT → READY → SENT → ACK → FIXED → PUBLIC
> Every row starts at **READY** and advances **only** by human action. The agent never sets a
> row past READY.

| Advisory | Engine | Status | Sent date | Ack date | Fixed date | Public date |
|---|---|---|---|---|---|---|
| `chroma.md`              | ChromaDB | **READY** | — | — | — | — |
| `milvus.md`              | Milvus   | **READY** | — | — | — | — |
| `weaviate.md`            | Weaviate | **READY** | — | — | — | — |
| `qdrant_pgvector_fyi.md` | Qdrant / pgvector | **READY** | — | — | — | — |

## Vendor security-contact channels (TEXT ONLY — informational; verify before use)
Channels listed for the human sender's convenience. **Confirm against each project's current
`SECURITY.md` before sending** — these can change. The agent has contacted no one.
- **ChromaDB** — GitHub private vulnerability report (`chroma-core/chroma` → Security →
  "Report a vulnerability") / the project `SECURITY.md`. Primary, preferred.
- **Milvus** — GitHub private advisory (`milvus-io/milvus` → Security) / `SECURITY.md`
  (Zilliz/LF AI & Data project security process).
- **Weaviate** — GitHub private advisory (`weaviate/weaviate` → Security) / `SECURITY.md`.
- **Qdrant** (FYI-tier) — GitHub private advisory (`qdrant/qdrant` → Security) / `SECURITY.md`.
- **pgvector** (FYI-tier) — GitHub repo `pgvector/pgvector` (single-maintainer OSS); use the
  repo's reporting guidance / `SECURITY.md` if present, else a private contact to the maintainer.

## Coordinated-disclosure policy (defaults; human confirms before sending)
- **Channel:** the project's private GitHub advisory / `SECURITY.md` / security@ (above).
- **Timeline:** 90 days standard; offer to extend; **no public PoC of inversion before fix/agreement.**
- **Provide on request:** versions tested, environment (`../results/ENV.txt`,
  `../requirements.lock.txt`), `../REPRODUCE.md`, the cited `../results/*.json` +
  `../scripts/phaseN_*.py`, the VEDC class, and the read-only auditor `../tool/vdbresidue.py`.
- **Tone:** collaborative, factual hardening guidance — not an accusation. Severity stated via
  VEDC class, not adjectives.

---
**Human gate:** to advance any row past READY, the human (a) verifies the channel against the
current `SECURITY.md`, (b) sends the advisory, (c) updates this tracker's Status + dates. The
agent stops here.
