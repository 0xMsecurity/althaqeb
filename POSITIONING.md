# ALTHAQEB — POSITIONING (decision of record)

> Output of the 2026-06-26 strategy/positioning research cycle. This is a **decision +
> integration map**, not a new pillar. It resolves the identity question and proposes one
> exact edit to `CONSTITUTION.md`'s North Star (flagged for **human ratification** — not
> silently applied). Research below is primary-source-cited; unsourced reasoning is labeled.
> NO FAKE RESULTS extends to strategy: no invented adoption, market size, or revenue.

## 1. The decision under test

> Is "neutral authority in AI security" (broad) the right identity — or is Althaqeb specifically
> the **erasure-durability / deletion-verification authority for AI memory systems** that
> integrates INTO the incumbents (MITRE ATLAS, OWASP, NIST AI RMF, ISO, GDPR Art. 17) rather
> than competing with them?

**Verdict: the narrow identity wins.** Althaqeb is the neutral authority on **whether deletion is
actually erasure in vector/RAG memory** — the one deletion layer no existing framework covers —
earned **tool-first**, with the VEDC standard as the compounding asset. (Candidate **B** as
identity, executed via candidate **C**'s sequencing; see §2.) The broad "MITRE for AI security"
framing is killed: that throne is taken and undefendable solo.

## 2. Tournament (pre-registered kills, evidence decides)

Candidates, deciding test = which identity maximizes the five success gates (independent
reproduction · vendor reaction · third-party reference · integration-not-isolation · neutrality
preserved) at lowest neutrality/funding risk, for a **solo founder**.

| Cand. | Identity | Verdict | Why (evidence) |
|---|---|---|---|
| **A** | Broad "MITRE for AI security" | **KILLED → GRAVEYARD** | MITRE ATLAS already owns the broad adversarial-AI taxonomy (ATT&CK-modeled, agentic+MCP coverage); OWASP/NIST own their layers. Competing on their turf solo fails Reviewer #2 + CEO + Reality. Re-confirms the already-buried "broad AI-security authority." |
| **B** | Erasure-durability / deletion-verification authority, **integrated** into ATLAS/NIST/ISO/GDPR | **WINNER (identity)** | The physical-residue layer is empty in all 6 frameworks (§3). Neutrality is a seat no vendor can hold (§4). Integration-not-isolation is the whole play (`INTEGRATION.md`). |
| **C** | DFIR/erasure **tool-first**; standard as a side effect | **WINNER (sequencing)** — merged into B | Not a rival to B: it is *how B is earned*. Authority bodies become cited via a free spec **plus** open-core tooling (§5). `vdbresidue` (tool) + VEDC (standard) is exactly that pairing. |
| **D** | Academic-first (preprint → citations → authority) | **KILLED as identity → GRAVEYARD** (retained as a *move*) | A paper decays and **commoditizes the method**, eroding the scarcity that is part of the moat (§4). Maintainer + Commercial + CEO kill it as the identity. A preprint is a useful authority-conferring *action*, not the position. |

**B and C are complements (identity vs sequencing), stated explicitly per the brief.** The merged
position: *be the erasure-durability authority (B), earn it tool-first with the standard as the
compounding asset (C), confer authority with selective academic/disclosure moves (D-as-tactic).*

## 3. Why the niche is real — the empty seam (cited)

"Deletion" is governed at the wrong layer everywhere; the **physical residue of a deleted
embedding in the vector store** is covered by nothing:

- **MITRE ATLAS — ABSENT.** Closest techniques are exposure/inversion of *live* data
  (`AML.T0057` LLM Data Leakage <https://atlas.mitre.org/techniques/AML.T0057>; `AML.T0024.001`
  Invert ML Model <https://atlas.mitre.org/techniques/AML.T0024>). No post-deletion residue /
  data-remanence technique. (LLM02→ATLAS crosswalk:
  <https://github.com/emmanuelgjr/GenAI-Security-Crosswalk/blob/main/llm-top10/LLM_MITREATLAS.md>)
- **NIST AI 600-1 — no erasure-verification control.** Term search of the official PDF:
  `erasure`/`right to be forgotten`/`RTBF`/`disposal` = 0 hits. Closest: `GV-1.7-002`
  decommissioning ("Data leakage after decommissioning"), `MG-4.1-006` "monitoring data
  deletions" for *provenance*. <https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf>
- **ISO/IEC 27001 A.8.10 — the strongest hook, but media-agnostic.** Requires deletion by methods
  making data *unrecoverable* with "verification processes to ensure that deleted information
  cannot be recovered" — yet no vector-store / HNSW / embedding method.
  <https://www.isms.online/iso-27001/annex-a-2022/8-10-information-deletion-2022/>
  **ISO/IEC 42001** (AI-specific) has **no** deletion control at all (Annex A.7 = data
  dev/acquisition/quality/provenance/preparation). <https://www.iso.org/standard/42001>
- **OWASP AISVS C8.3 — closest in AI, still retrieval-only.** `C8.3.1` "expired vectors are
  excluded from retrieval results"; `C8.3.2` "memory can be reset" — logical exclusion, **not**
  physical unrecoverability.
  <https://github.com/OWASP/AISVS/blob/main/1.0/en/0x10-C08-Memory-Embeddings-and-Vector-Database.md>
- **GDPR Art. 17 — obligation, no method/proof.** Only "reasonable steps, including technical
  measures." <https://gdpr-info.eu/art-17-gdpr/> The EDPB's 2025 Coordinated Enforcement review
  found controllers cannot reliably *demonstrate* erasure.
  <https://www.edpb.europa.eu/news/news/2026/edpb-identifies-challenges-hindering-full-implementation-right-erasure_en>
  Stored embeddings invert back to PII <https://www.tonic.ai/blog/sensitive-data-in-text-embeddings-is-recoverable>.
- **Machine-unlearning verification — model-centric and forgeable.** Verifies whether the *model*
  forgot (membership inference / influence), shown circumventable. Silent on raw vectors on disk.
  Survey <https://arxiv.org/abs/2506.15115>; fragility <https://arxiv.org/abs/2408.00929>.

**Seam:** an executable, measured standard for *vector-store erasure durability* — how long a
logically-deleted embedding stays physically recoverable (HNSW residue, invertible to text), and
a per-engine class. That is exactly VEDC + `vdbresidue`. Our exact delta vs prior art (Stahlberg
SIGMOD'07, Reardon SoK'13, GDPR 17) is already pinned in `standards/erasure-durability/SPEC.md` §7.

## 4. The moat (cited facts + labeled inference)

- **Niche real and unoccupied (4/4 adjacent industries stop short of the seam).** Vendors
  document the residue **as a performance/storage issue, never security** — Weaviate tombstones +
  `cleanupIntervalSeconds` <https://docs.weaviate.io/weaviate/config-refs/indexing/vector-index>;
  Qdrant "deletions as soft deletes using a bitmask… Vacuum Optimizer"
  <https://qdrant.tech/documentation/faq/qdrant-fundamentals/>; Milvus "Is storage space released
  right after deletion? No" <https://milvus.io/docs/product_faq.md>; Chroma HNSW residue issues
  <https://github.com/chroma-core/chroma/issues/2594>. GRC verifies the *workflow ran* (BigID's
  scan vs deletion are two unconnected products <https://bigid.com/data-deletion/>); media vendors
  verify the *medium* (Blancco <https://blancco.com/products/drive-eraser/>); DFIR recovers *bytes*
  but no tool decodes them as embeddings (Autopsy SQLite "ignores blobs"
  <https://github.com/markmckinnon/Autopsy-Plugins/blob/master/Parse_SQLite_Databases/README.md>).
- **The discovery is NOT the moat.** "Delete is not enough" is in the vendors' own docs; vec2text
  is public <https://arxiv.org/abs/2310.06816>; `vdbresidue` is rebuildable in months. **The moat
  is position + persistence, not technical secrecy.**
- **The durable advantages** (ANALYSIS, grounded in the above): (1) **structural neutrality** — no
  vendor can credibly audit its own erasure; a third party that audits all engines on one yardstick
  holds a seat incumbents cannot; (2) **cross-engine maintenance burden** (N engines × versions)
  deters dabblers; (3) **evidence-traceability** (committed results + NO-FAKE gate) is a trust brand
  vendor marketing and one-shot papers can't fake; (4) **read-only/defensive posture** deployable
  in DFIR/GDPR where a vendor tool or offensive PoC is not.
- **Biggest threat:** a GRC/privacy incumbent (BigID nearest — already scans vector DBs) bolting on
  "deletion verification" and winning on distribution. **Counter:** a GRC vendor is *another vendor
  selling to the same buyer* and cannot neutrally audit a vendor (or itself). Neutral-authority +
  standard-adoption is the axis it cannot occupy. *Secondary threat:* an open academic benchmark
  commoditizing the method — countered by owning the *maintained registry + conformance tool +
  Confirmed/Provisional evidence levels* a paper does not sustain.
- **Honest bound:** 3–5-year defensibility is **conditional on converting the head start into
  citation/standard-adoption**, not on technology. Code alone does not hold the niche; *being the
  reference* does.

## 5. How to sustain neutral authority + funding (cited; the CIS open-core template)

Every body that became cited-by-default did it the same way — and the failure modes are the same:

- **Mechanism 1 — ship a FREE, openly-licensed common spec/IDs.** CVE IDs
  <https://www.cve.org/About/Overview>, ATT&CK technique IDs at no charge
  <https://attack.mitre.org/resources/faq/>, OWASP Top 10 free awareness doc
  <https://owasp.org/www-project-top-ten/>, CVSS/EPSS/TLP licensed freely
  <https://www.first.org/cvss/v4.0/specification-document>, CIS Benchmarks free PDFs
  <https://www.cisecurity.org/cis-benchmarks-overview>. → **Keep VEDC SPEC + `vdbresidue` core free
  and openly licensed.**
- **Mechanism 2 — monetize the IMPLEMENTATION layer, not the spec (CIS open-core).** CIS fences the
  free spec (CC BY-NC-SA, commercial use carved out
  <https://www.cisecurity.org/terms-of-use-for-non-member-cis-products>) and charges for *applying*
  it: free-Lite→paid-Pro assessor funnel, Build Kits, usage-metered Hardened Images, tiered
  membership with academia/government free
  <https://www.cisecurity.org/cis-securesuite/pricing-and-categories>. Neutrality survives because
  revenue is on convenience/automation, never the recommendations. → **Open-core for Althaqeb: free
  neutral VEDC + auditor; paid assessment / certification / DFIR / managed erasure-verification.**
- **Mechanism 3 — get cited-by-reference via cross-framework mapping.** OWASP←PCI DSS Req 6; CIS
  Benchmarks map to NIST/ISO/PCI/HIPAA and are DoD-IL2 accepted
  <https://www.cisecurity.org/cybersecurity-tools/mapping-compliance/mapping-and-compliance-with-the-cis-benchmarks>;
  NIST AI RMF shipped crosswalks. → **`INTEGRATION.md` is this move; target an OWASP AISVS C8.3.4
  PR and an ISO 27001 A.8.10 operationalization note.**
- **Trap 1 — single-funder dependence (existential, realized repeatedly in 2025).** MITRE's CVE
  program nearly lapsed in ~24h on one expiring contract
  <https://krebsonsecurity.com/2025/04/funding-expires-for-key-cyber-vulnerability-database/>; the
  CVE Foundation named the diagnosis — "sustainability and neutrality… tied to a single government
  sponsor" — and prescribed diversified funding
  <https://www.thecvefoundation.org/newsroom/posts/2025-04-16-launch>. CIS's MS-ISAC lost 21 years
  of CISA funding on 2025-09-30 <https://www.theregister.com/2025/09/30/cisa_kills_cis_agreement/>.
  → **Diversify from day one; never tie Althaqeb's existence to one sponsor.**
- **Trap 2 — letting the funder write the spec (capture).** OWASP shipped a 2017 Top-10 draft
  recommending WAF/RASP "unilaterally added by… a RASP vendor," reversed after backlash
  <https://github.com/OWASP/Top10/issues/72>; CVSS lets scored vendors self-assign
  <https://www.first.org/cvss/v4.0/specification-document>. → **Hard separation between whoever
  funds Althaqeb and the VEDC registry content; keep the evidence-gate + NO-FAKE structural (it
  already is). This is the Ethics seat's standing watch item.**

## 6. Proposed CONSTITUTION edit — FOR HUMAN RATIFICATION (do not auto-apply)

Current North Star (`CONSTITUTION.md` §NORTH STAR, line 32): *"Althaqeb exists to become a
**neutral authority in AI Security**. Not a product. Not a paper. Not a collection of scripts.
Authority."*

**Proposed replacement (sharper, defensible, integration-first):**

> Althaqeb exists to become the **neutral authority on erasure durability in AI memory systems** —
> defining and measuring whether *deletion is actually erasure* in vector/RAG stores (the VEDC
> standard + the read-only `vdbresidue` auditor), and **integrating that measurement into** the
> frameworks that govern deletion (GDPR Art. 17, ISO/IEC 27001 A.8.10 & 42001, NIST AI RMF, OWASP
> AISVS, MITRE ATLAS) rather than competing with them. Not a product. Not a paper. Not a collection
> of scripts. Authority — earned tool-first, with the standard as the compounding asset.

The ladder (Research→…→Standards→Certification→Authority) is unchanged; this narrows the *domain*
from "AI security" (taken) to "erasure durability in AI memory" (open). **A human ratifies this
edit; the agent will not rewrite the constitution unilaterally.**

## 7. Board verdict

No seat kills B+C. **Authority** — clear citation path (AISVS C8.3.4, ISO A.8.10, NIST crosswalk).
**CEO** — 1/3/5-yr moat real but adoption-conditional; favors the narrow identity. **Commercial** —
CIS open-core fits exactly; neutral core preserved. **Reviewer #2** — niche proven empty across 6
frameworks + unlearning literature; SPEC §7 pins the delta. **Ethics** — dual-use handled
defensive-first; Trap 2 is the standing watch item (funders ≠ registry). **Reality (veto)** — every
claim traces to a primary source or committed result; passes. **A and D killed to GRAVEYARD.**

## 8. Open questions (honest; not forced closed)

- ATLAS-as-AI-taxonomy *mechanism* not separately sourced (mirrors ATT&CK, unverified). 
- No authoritative regulator text says verbatim "deleting from a vector DB is not sufficient" — it
  is our empirical contribution, supported by Art. 17's silence + EDPB + inversion literature.
- Whether OWASP AISVS will accept a storage-layer C8.3.4 is unknown until proposed (a *move*, not a
  claim).
- No primary evidence that vendor participation has *realized* benchmark capture at CIS/FIRST — the
  risk is structural, which is why Trap 2 is a control, not a prediction.
