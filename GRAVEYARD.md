# ALTHAQEB — GRAVEYARD

> Dead directions are assets. We keep *why* each died so future selves do not resurrect
> corpses, re-litigate settled kills, or mistake fashion for evidence. Resurrection
> requires **genuinely new evidence**, not renewed enthusiasm. This file is the in-repo
> copy of the kill record (it previously lived only in external session memory — a
> durability gap now closed).

Today's anchor date for "recent": 2026-06-23.

---

## Killed directions (do NOT resurrect without new evidence)

- **Product ideas (general)** — died across multiple destruction cycles.
- **Prompt-injection scanners / URL-API scanners** — crowded, low durable authority, died.
- **Runtime firewall / observability products** — died.
- **MCP-security platform / "agent platform" ideas** — died.
- **Broad "Agent Memory Forensics" angle** — too broad; weakened by existing provenance
  + secure-deletion literature; narrowed to the residue kernel.
- **MemAudit / MemLineage-style tooling claims** — overlapped with 2026 prior art
  (MemAudit, MemLineage); multiple sub-claims destroyed. The residue kernel is what
  survived *because* it is narrower and empirically anchored.
- **Taxonomy-first papers** — taxonomy is a side effect of evidence, not a starting point.
- **Plaintext / WAL residue as the headline** — real but **transient** (purged by
  compaction within ~1–1.5k writes); un-novel (Stahlberg SIGMOD'07 already showed
  deleted records persist). Reviewer #2 FATAL. Buried. The *durable HNSW vector* residue
  that survives compaction is the novel replacement.
- **Six major paper designs** — died before the current kernel survived. Do not rebuild them.

---

## Self-correction log (beliefs reality overturned)

- **"HNSW shows no residue after delete"** (early experiment-1) → WRONG. That run used a
  single record with no compaction, so the vector never flushed WAL→HNSW. Corrected:
  HNSW residue is real and durable, but only **after** a WAL→HNSW flush.
- **"Durable across all append-only-segment engines"** → TOO STRONG. Corrected to: a
  recovery *window* is universal, but only ChromaDB is *unbounded*; Qdrant-server and
  pgvector demonstrably purge via built-in maintenance.
- **"Weaviate is durable without intervention"** → WRONG; that was a too-short (20s)
  observation window. Weaviate auto-purges via tombstone cleanup (~70s at interval=5s,
  default 300s). It belongs with Qdrant/pgvector, not Chroma.
- **"High delete ratio purges everywhere"** → PARTIALLY REFUTED. Chroma is
  ratio-independent (never reclaims); Milvus high-ratio triggered compaction but did not
  yield observable purge within the tested window (later: GC ~360s after a *completed*
  compaction).

---

## How directions die here (the kill chain — run before any new effort)

An idea must survive all of these or be killed immediately:

1. **Novelty** — did someone already do this? (Assume Reviewer #2 has read more.)
2. **Reviewer #2** — what destroys the contribution?
3. **Threat model** — why would anyone care?
4. **Engineering** — can it actually be built and maintained?
5. **Reproducibility** — will it still work next year, by a stranger?
6. **Adversarial** — can it be bypassed/evaded?
7. **Economic** — is it worth the resources?
8. **Maintenance** — does it survive growth?
9. **Community** — will experts dismiss it?
10. **Time** — will it matter in five years?

Rule: if **three board seats independently vote to kill**, it dies. No appeals, no
renaming, no scope expansion, no building a platform around a corpse.

---

## The single surviving kernel

Deletion residue in vector databases → see [`STATE.md`](STATE.md) and
[`experiments/residue/FINDINGS.md`](experiments/residue/FINDINGS.md). Everything else
above is dead and stays dead absent new evidence.
