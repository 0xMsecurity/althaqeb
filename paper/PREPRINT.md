# Deletion Is Not Erasure: Measuring Vector-Store Erasure Durability in AI Memory Systems

> **STATUS: DRAFT — NOT SUBMITTED.** Staged for human review. Submission to arXiv (or anywhere)
> is an external emission under the human author's name and is a Human Gate (autopilot §4). Every
> quantitative claim below cites a committed result file under `experiments/residue/results/`; no
> number is asserted. URLs for external frameworks are in [`../POSITIONING.md`](../POSITIONING.md)
> §3 (single source of truth). Author/affiliation: **TO BE SET BY HUMAN**.

## Abstract

Retrieval-augmented and agent-memory systems store user content as embedding vectors in
vector/RAG databases. When a record is deleted — including to satisfy a GDPR Art. 17 erasure
request — the engine performs a *logical* delete: the API reports the record gone, but the
embedding can persist **physically** on disk until an asynchronous reclamation pass runs, if ever.
We show that this residual embedding is (i) recoverable by a **blind byte-parse of the
approximate-nearest-neighbor (ANN) segment with no schema, IDs, or API access**; (ii)
**self-identifying** on several engines, because the engine's own deletion metadata selects exactly
the erased records; and (iii) **invertible back to source text**, making "opaque floats" recoverable
PII. We define **VEDC** (Vector-store Erasure Durability Classification), an executable,
positive-control-gated standard that measures how long a logically-deleted embedding remains
physically recoverable and assigns each engine a class (N → M → AU → AT → U, optional `+S` for
self-identifying deletion). Across **10 engines**, 7 expose a post-delete recovery window;
**ChromaDB is the unique unbounded (`VEDC-U+S`) case** — no reclamation observed across 50k writes,
restarts, collection-drop, idle, and four reclaim attacks — while every other engine reclaims on a
timer, a maintenance command, or at write. The principle "deletion ≠ secure erasure" is decades old
for physical media (NIST SP 800-88, IEEE 2883); our contribution is the **method, measurement, and
cross-engine classification for AI memory**, a layer no existing security or data-protection
framework covers.

## 1. Introduction

"Delete from the vector DB" is the assumed right-to-be-forgotten path for RAG/agent systems, and is
widely documented as insufficient — but only as a *performance/storage* footnote in vendor docs,
never as a measured erasure property. No framework closes the gap: MITRE ATLAS has no post-deletion
residue technique; NIST AI RMF / 600-1 has no erasure-verification control; OWASP AISVS C8.3 checks
only *retrieval exclusion*; ISO/IEC 27001 A.8.10 mandates verified-unrecoverable deletion but is
media-agnostic; GDPR Art. 17 imposes the obligation with no method or proof standard; and
machine-unlearning verification targets the *model*, not the on-disk vector (and is itself
forgeable). The exact-delta argument is developed in §6 and in the VEDC SPEC §7.

We contribute: (1) a **threat model** for vector-store data remanence; (2) **VEDC**, an executable
classification with a mandatory positive control and Confirmed/Provisional evidence levels; (3) a
**10-engine measurement**; (4) the **ChromaDB unbounded** finding with cross-version confirmation;
and (5) a read-only auditor (`vdbresidue`) that turns the method into a defensive
erasure-verification tool.

## 2. Threat model

**Asset:** content a data subject or operator believes was deleted (PII, secrets, poisoned RAG
entries). **Adversary capability:** read access to the persistence directory or object store — a
host operator, a backup/snapshot, a shared or multi-tenant volume, or a decommissioned disk. **Not**
a remote/network bug. **Goal:** recover deleted content. **Aggravating factor:** when deletion is
self-identifying (`+S`), recovery is *targeted* at exactly the erased records rather than requiring a
scan of all data. This is a confidentiality/compliance threat (erasure ineffectiveness), honestly
Low–Medium depending on deployment, not a memory-safety or RCE class.

## 3. Method: VEDC

For each engine: insert known "poison" vectors + filler; confirm logical deletion (count/`get`
empty); apply the engine's reclamation surface (idle, churn, optimizer, VACUUM, compaction); and at
each checkpoint **byte-scan the raw store** for the float32 (and L2-normalized) vector bytes. A
**mandatory positive control** — a live filler vector that must remain present — validates that the
scanner works at each checkpoint; a trial whose positive control fails is *invalid and discarded*,
never counted as evidence of erasure (anti-gaming, SPEC §4). Classes (SPEC §5):

- **VEDC-N** none (reclaimed at write/close) · **VEDC-M** manual-only (explicit command) ·
  **VEDC-AU** auto/untimed · **VEDC-AT** auto/timed (purge time measured) · **VEDC-U** unbounded.
- **`+S`** when the engine's deletion metadata self-identifies the residue.
- **Conformance:** *Confirmed* (≥3 valid seeds / cross-version / multi-condition) vs *Provisional*
  (single trajectory).

The detector is **float32-exact** (cosine > 0.999); its quantized blind spot is stated in §8 and
SPEC §9, which is why `VEDC-N` is **format-scoped**.

## 4. Results — cross-engine

Every cell traces to the gated registry (`benchmarks/deletion-durability/registry.json`) and its
cited `results/*.json`; classification roster in `standards/erasure-durability/CLASSIFICATION.md`.

| Engine | VEDC class | Reclamation trigger | Conformance | Key evidence |
|---|---|---|---|---|
| **ChromaDB** 1.5.9 | **VEDC-U+S** (unbounded) | none observed | Confirmed (5 seeds + cross-version + attacks) | `phase2_seed0`, `phase6_blind_deletemark`, `phase12/13/16`, `phase7_audit`, `cross_version_chroma_summary` |
| Milvus 2.5.10 | VEDC-AT+S | GC ~360s after completed high-ratio compaction | Provisional (multi-condition) | `phase11`, `phase12_milvus_highratio`, `phase15_milvus_gctimeline` |
| Weaviate 1.28.2 | VEDC-AT | async tombstone cleanup ~70s | Confirmed (×3 seeds) | `phase10`, `phase14_weaviate_cleanup`, `phase19_weaviate_multiseed` |
| Qdrant server 1.18.2 | VEDC-AU | vacuum optimizer | Confirmed (×3+ seeds) | `phase9`, `phase22_qdrant_multiseed`, `phase26_qdrant_pinned` |
| pgvector HNSW index 0.8.3 | VEDC-AU | plain `VACUUM` | Confirmed (×3 seeds) | `phase8_pgvector_hnsw{,_seed1,_seed2}` |
| Postgres heap (bytea/TOAST) | VEDC-M+S | `VACUUM FULL` (survives plain VACUUM) | Confirmed (×3 seeds) | `phase4_postgres{,_seed1,_seed2}` |
| LanceDB | VEDC-M+S | explicit compaction (~10% per-fragment threshold) | Confirmed (×3 seeds) | `phase25_lancedb` |
| sqlite-vec | VEDC-N | vec0 chunk rewrite at delete | Confirmed (×3 seeds) | `phase24_sqlite_detector` |
| FAISS (flat) | VEDC-N | reserialize-on-write | Provisional (neg. control) | `phase3_cross_backend` |
| Qdrant local/embedded | VEDC-N | rewrite-on-close | Provisional (neg. control) | `phase3_cross_backend` |

**Reading:** 7/10 expose a post-delete window; **ChromaDB is the only unbounded class.** The others
reclaim — but reclamation is deferred to a pass that does not run by default (timer, optimizer,
`VACUUM`, compaction), so a window exists in every positive engine.

## 5. Results — ChromaDB deep dive (the headline)

- **Bit-identical residue (`phase1_seed0`).** After `delete` + compaction (logical count 0, WAL
  plaintext hits 0), all **5/5** poison vectors are present **bit-identical** in `data_level0.bin`;
  blind-parse match cosine **1.0** for all five.
- **Deletion self-identifies the residue (`phase6_blind_deletemark`).** Reading only the raw segment
  (no IDs/schema), the hnswlib `DELETE_MARK` bit selects **exactly the 5 deleted** elements out of
  **3005** — inverting normal forensic difficulty (recover 5, not 3005).
- **Invertible to text (`phase1_seed0`).** vec2text (gtr-base) reconstructs trigger-bearing text from
  the residue: re-embed cosine **0.893–0.972**, trigger-token preservation **0.8–1.0**.
- **Specific, not hallucinated (`phase1_seed0`).** Poison-token overlap **4.0** for POISON residue
  vs **0.0** for BENIGN and **0.0** for RANDOM filler — the inverter is recovering the actual deleted
  content, not generic security text.
- **Unbounded.** Survives 50k inserts + 3 restarts + `delete_collection` (`phase2`), 360s idle
  (`phase16`), a 60% high-ratio delete (`phase12`, 5/5 still present), and four reclaim attacks
  (`phase13`); **architectural** across 0.5.23 → 1.5.9 incl. the 1.0 Rust rewrite
  (`cross_version_chroma_summary`); independently replicated on the default MiniLM-L6-v2 (dim 384)
  with realistic PII, **8/8** recovered (`phase7_audit`).

## 6. Related work / exact delta

Full treatment in VEDC SPEC §7. In brief: the *persistence phenomenon* (Stahlberg SIGMOD'07; Reardon
SoK'13) and the *verify-erasure principle* (NIST SP 800-88 Rev. 2, IEEE 2883-2022 — at the media
layer, ML/embeddings out of scope; ISO 27001 A.8.10 — media-agnostic; GDPR Art. 17 — obligation, no
method) are **prior art and conceded**. MITRE ATLAS, NIST AI 600-1, OWASP AISVS C8.3, and
machine-unlearning verification each stop short of on-disk vector residue. **Ours:** blind ANN-segment
recovery, self-identifying deletion, embedding-to-text inversion, unbounded-on-Chroma, and an
executable cross-engine VEDC classification. No "first" is claimed beyond this delta.

## 7. Ethics & responsible disclosure

Dual-use: the method verifies GDPR erasure (defensive) and also recovers "deleted" vectors
(offensive). We frame for the defensive case and ship a **read-only** auditor (never mutates a
target). Engine-specific findings are handled under **coordinated disclosure**
(`experiments/residue/disclosure/`), at honest, non-sensational severity (Low–Medium, filesystem-
access-gated), with **no public inversion PoC before vendor agreement**. No vendor has been contacted
at the time of this draft; disclosure is gated on the human author and should follow priority-staking
(this preprint) per standard coordinated-disclosure practice.

## 8. Limitations (honest)

- **Float32-exact detector** — quantized residue evades it. Measured envelope (`phase5_quantization`):
  scalar-int8 dequantizes to cosine **0.9996** and still inverts (trigger **0.80**); PQ-m96
  cosine 0.856 / trigger **0.40**; 1-bit cosine 0.799 / trigger **0.24**. So "no float32 residue" ≠
  "no recoverable residue"; **`VEDC-N` is format-scoped** (SPEC §9). A quantization-aware detector is
  acknowledged future work.
- **Inversion tested on gtr-base** (vec2text ships gtr / ada-002); residue *existence* and recovery
  are model-independent, but text-reconstruction quality depends on model + precision + inverter
  availability.
- **Milvus is Provisional** (multi-condition, not multi-seed) — a deferred 3-container run, by cost
  decision, not an evidence gap.
- **Negative controls** (FAISS, Qdrant-local) are single-run by design.

## 9. Reproducibility

Pinned environment (`experiments/residue/requirements.lock.txt`, `results/ENV.txt`), fixed seeds,
chain-of-custody manifest (`MANIFEST.sha256`, `verify_manifest.sh`), and per-phase scripts
(`scripts/phaseN_*.py`). Two mechanical integrity gates re-run in CI: the registry evidence gate
(every cited result must exist) and the VEDC conformance gate. Steps in `REPRODUCE.md`.

## 10. Conclusion

In AI memory systems, deletion is a logical operation; physical erasure is a separate, often-deferred
event that may never occur. VEDC makes this measurable and comparable across engines, and identifies
ChromaDB as the unique unbounded case. The defensive takeaway is concrete: operators can no longer
assume "deleted from the vector DB" means "erased," and now have a read-only way to verify it.
