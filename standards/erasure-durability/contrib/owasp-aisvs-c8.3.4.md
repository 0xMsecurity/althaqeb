# Staged contribution — OWASP AISVS C8.3.4 (physical unrecoverability of deleted embeddings)

> **STATUS: DRAFT, staged. The PR is NOT opened.** Opening a PR against `OWASP/AISVS` is an
> external emission under the human's identity (autopilot §4 gate). This file holds the proposed
> requirement text, the rationale, and the exact diff so a human can open it verbatim.
> Target file: `OWASP/AISVS` → `1.0/en/0x10-C08-Memory-Embeddings-and-Vector-Database.md`.

## Why (the gap, sourced)

AISVS C8.3 ("Memory Expiry & Revocation") currently verifies the **retrieval/logical** layer only:
- C8.3.1 "Verify that expired vectors are excluded from retrieval results."
- C8.3.2 "Verify that memory can be reset."
- C8.3.3 "Verify that quarantined content is retained but excluded from all retrieval results."

None checks whether a deleted/expired embedding is **physically unrecoverable** from the store. This
is exactly the failure mode that matters for erasure/RTBF: across 10 engines, a logically-deleted
embedding commonly persists **bit-identical** in the ANN segment after the API reports it gone, is
recoverable by a blind byte-parse with no schema/IDs, and is **invertible back to source text**;
on some engines (ChromaDB) the residue is **unbounded**. Retrieval-exclusion (C8.3.1) is satisfied
while the vector still sits on disk. The control set therefore has a real, demonstrable hole.

## Proposed new requirement (AISVS table row)

| # | Description | Level |
|---|---|---|
| **C8.3.4** | **Verify that a deleted or expired embedding is *physically unrecoverable* from the underlying store — i.e. no residual vector remains in the ANN index / segment files, and any residual cannot be inverted back to its source content — and not merely excluded from retrieval results.** Where physical reclamation is deferred to a background compaction/vacuum/optimizer, verify the bounded reclamation window is documented and acceptable for the data's erasure requirements. | 2 |

(Level 2 proposed to match the other C8.3 items; maintainers may re-level.)

## Rationale / evidence (for the PR body)

- Logical delete ≠ physical erasure in vector stores; the residual embedding is recoverable content
  (invertible to text), so retrieval-exclusion is insufficient for erasure/RTBF.
- A free, read-only verification method exists and is practical for an audit: the **VEDC** standard
  (Vector-store Erasure Durability Classification) and the `vdbresidue` auditor, which classifies an
  engine's reclamation behavior (N / M / AU / AT / U, `+S` if deletion self-identifies the residue)
  and exits non-zero when recoverable deleted residue is found.
- This requirement is engine-agnostic and testable today against Chroma, Milvus, Weaviate, Qdrant,
  pgvector, LanceDB, sqlite-vec.

## References to cite in the PR

- VEDC standard (SPEC + classification roster) — `standards/erasure-durability/`.
- Method/measurement preprint — `paper/PREPRINT.md` (cite the arXiv ID once the human submits).
- `vdbresidue` read-only auditor — `experiments/residue/tool/` (v0.1.0).
- Prior-art framing (NIST SP 800-88 / IEEE 2883 media layer; ISO 27001 A.8.10 media-agnostic;
  the AI-memory delta) — VEDC SPEC §7.

## Exact diff to propose (insert after the C8.3.3 row)

```diff
 | C8.3.3 | Verify that quarantined content is retained but excluded from all retrieval results. | 2 |
+| C8.3.4 | Verify that a deleted or expired embedding is physically unrecoverable from the underlying store (no residual vector in the ANN index / segment files; any residual not invertible to source content), not merely excluded from retrieval results. Where physical reclamation is deferred to a background compaction/vacuum/optimizer, verify the bounded reclamation window is documented and acceptable for the data's erasure requirements. | 2 |
```

## Human action to clear this gate

1. Confirm the exact current C8.3 row IDs/levels in the upstream file (it evolves).
2. Open a PR on `OWASP/AISVS` adding C8.3.4, body = the rationale + references above. Best opened
   **after** the preprint is on arXiv so the PR can cite a stable ID (priority-staking).
3. Engage maintainer feedback; re-level if asked. Do not assert adoption until merged.
