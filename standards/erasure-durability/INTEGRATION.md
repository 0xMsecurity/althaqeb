# VEDC — Framework Integration / Crosswalk

> The artifact that makes Althaqeb **adopted-as-complement, not dismissed-as-competitor**.
> VEDC is not a rival to these frameworks; it is the missing **measurement primitive** that
> operationalizes the deletion clauses each leaves abstract. Every hook is primary-source-cited.
> Positioning rationale: see [`../../POSITIONING.md`](../../POSITIONING.md); class definitions:
> [`SPEC.md`](SPEC.md) §5; live roster: [`CLASSIFICATION.md`](CLASSIFICATION.md).

## The layer map — where "deletion" is governed today

| Layer | Question answered | Framework that owns it | Covers vector-store residue? |
|---|---|---|---|
| Legal obligation | "Must we erase on request?" | GDPR Art. 17 | No — no method, no proof standard |
| Model behavior | "Did the *model* forget?" | Machine-unlearning verification | No — model-centric, and forgeable |
| Retrieval layer | "Is it excluded from results?" | OWASP AISVS C8.3 | No — logical exclusion only |
| Generic storage | "Is media wiped & verified?" | ISO/IEC 27001 A.8.10 | No — media-agnostic, vector-blind |
| AI governance | "Do we have a lifecycle?" | NIST AI 600-1 / ISO 42001 | No — retention/decommission only |
| Attacker TTPs | "How is data exposed/inverted?" | MITRE ATLAS | No — no post-deletion residue technique |
| **Physical residue in the store** | **"Is the deleted embedding still recoverable / invertible?"** | **— empty —** | **VEDC fills this** |

## The three strongest mappings (lead with these)

### 1. ISO/IEC 27001:2022 Annex A 8.10 — Information deletion  *(strongest hook)*
- **Clause:** deletion must use methods that render data *unrecoverable*, with "verification
  processes to ensure that deleted information cannot be recovered."
  <https://www.isms.online/iso-27001/annex-a-2022/8-10-information-deletion-2022/>
- **The gap:** A.8.10 is **media-agnostic** — it mandates verified unrecoverability but defines no
  method for an ANN index / HNSW segment / embedding store, and does not recognize that a logical
  vector-DB delete leaves a recoverable embedding.
- **What VEDC supplies:** the vector-store-specific verification method A.8.10 demands but does not
  define. A `VEDC-N` (Confirmed) result *is* A.8.10 evidence that the deletion is unrecoverable for
  the tested format; a `VEDC-U/AU/AT/M` result is evidence it is **not** (yet). **VEDC = A.8.10 made
  executable for AI memory.**

### 2. GDPR Article 17 — Right to erasure  *(highest-stakes hook)*
- **Clause:** obligation to erase "without undue delay"; only "reasonable steps, including technical
  measures." <https://gdpr-info.eu/art-17-gdpr/> No method, no proof standard.
- **The gap (regulator-confirmed):** EDPB's 2025 Coordinated Enforcement review found controllers
  cannot reliably *demonstrate* erasure.
  <https://www.edpb.europa.eu/news/news/2026/edpb-identifies-challenges-hindering-full-implementation-right-erasure_en>
  And a stored embedding still carries the PII (invertible to text)
  <https://www.tonic.ai/blog/sensitive-data-in-text-embeddings-is-recoverable>.
- **What VEDC supplies:** the *technical-measure evidence* Art. 17 omits — a measured durability
  class per engine, so a controller can demonstrate whether an RTBF deletion is actually
  unrecoverable. `+S` (self-identifying deletion) is the aggravating factor: it makes *targeted*
  recovery of exactly the erased records feasible during the window.

### 3. OWASP AISVS C8 — Memory, Embeddings & Vector Database  *(fastest adoption path)*
- **Clause:** C8.3.1 "expired vectors are excluded from retrieval results"; C8.3.2 "memory can be
  reset"; C8.3.3 quarantined content "excluded from all retrieval results."
  <https://github.com/OWASP/AISVS/blob/main/1.0/en/0x10-C08-Memory-Embeddings-and-Vector-Database.md>
- **The gap:** C8.3 verifies *retrieval-level exclusion* (logical delete) — exactly the failure mode
  where the vector still resides in the HNSW graph on disk. It never checks physical unrecoverability.
- **What VEDC supplies & the move:** a proposed **C8.3.4** — *"Verify that a deleted embedding is
  physically unrecoverable from the store (no HNSW/heap residue; not invertible to source text),
  per its VEDC class."* This is a natural upstream PR and the single highest-EV authority-conferring
  integration (community-owned, fast, no accreditation ecosystem required). **The full requirement
  text, rationale, and exact diff are staged** in [`contrib/owasp-aisvs-c8.3.4.md`](contrib/owasp-aisvs-c8.3.4.md)
  — ready for a human to open the PR (opening it is a gate; do it after the preprint has an arXiv ID
  so the PR cites a stable reference).

## Secondary mappings

### NIST AI RMF + 600-1 GenAI Profile
- **Hooks:** `GV-1.7-002` decommissioning ("Data leakage after decommissioning"); `MG-4.1-006`
  "monitoring data deletions" for provenance. <https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf>
  (`erasure`/`RTBF`/`disposal` = 0 hits in the Profile.)
- **What VEDC supplies:** a concrete MEASURE-function test ("verify deleted embeddings are
  unrecoverable") the Profile names nowhere; pairs with `GV-1.7-002` to make "data leakage after
  decommissioning" measurable rather than advisory. Delivered as a NIST-style crosswalk row.

### ISO/IEC 42001 — AI management system
- **Hook:** Annex A.7 (A.7.2–A.7.6) governs the AI data lifecycle but has **no** deletion/disposal
  control. <https://www.iso.org/standard/42001>
- **What VEDC supplies:** a deletion-durability control candidate for the A.7 lifecycle, closing the
  end-of-life gap 42001 currently defers to GDPR/27001.

### MITRE ATLAS / OWASP LLM Top 10 (LLM02:2025)
- **Hook:** LLM02 maps to ATLAS `AML.T0057`, `AML.T0024.001` (Invert ML Model)
  <https://github.com/emmanuelgjr/GenAI-Security-Crosswalk/blob/main/llm-top10/LLM_MITREATLAS.md>.
- **What VEDC supplies:** a candidate ATLAS technique — *"Recover Deleted Embedding (vector-store
  data remanence)"* — sitting between Collection and Exfiltration. The residue VEDC measures is the
  **precondition** that makes `AML.T0024.001` exploitable *after* a delete. (Lower-probability move:
  ATLAS contribution bar is higher than an AISVS PR.)

### Machine-unlearning verification literature
- **Hook:** verifies "did the *model* forget?" and is provably forgeable
  <https://arxiv.org/abs/2506.15115>, <https://arxiv.org/abs/2408.00929>.
- **What VEDC supplies:** the orthogonal, storage-side complement — "is the *raw vector* still
  recoverable on disk?" — a property independent of model weights and **not forgeable** because it is
  measured directly against the store. Positions VEDC as the missing half, not a competitor.

## Per-class → obligation reading (how an auditor uses the roster)

| VEDC class | Erasure meaning | A.8.10 / Art. 17 reading |
|---|---|---|
| **VEDC-N** | No recoverable residue (format-scoped, §9) | Meets "unrecoverable" for the tested format — passing evidence |
| **VEDC-M(+S)** | Purged only by an explicit operator command | Conditional — erasure requires a documented manual step (e.g. `VACUUM FULL`) |
| **VEDC-AU / AT** | Auto-reclaimed (untimed / timed) | Bounded exposure window; erasure SLA = the reclaim interval; document it |
| **VEDC-U(+S)** | Unbounded — no reclamation observed | **Fails** "unrecoverable"; deletion is logical only. `+S` ⇒ targeted recovery feasible |

> **Caveat carried from SPEC §9:** `VEDC-N` is **format-scoped** — it rules out residue only for the
> storage format actually measured (the float32 detector does not see quantized residue). An auditor
> must not read `VEDC-N` as "unrecoverable in all formats."

## Net positioning statement

VEDC is the executable bridge between the *legal/governance obligation to erase* (GDPR 17, NIST
600-1, ISO 42001) and the *generic verified-deletion requirement* (ISO 27001 A.8.10), specialized
for vector/RAG storage — the exact layer ATLAS, OWASP LLM02, AISVS C8.3, and machine-unlearning
verification all stop short of.
