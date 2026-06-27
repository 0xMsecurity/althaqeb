# RESULTS — raw observations (ARCHIVED / SUPERSEDED)

> **Superseded early-exploration snapshot (EXP 01–05).** These are the first five
> exploratory experiments, kept verbatim for provenance. The current, evidence-gated
> record is [`../residue/FINDINGS.md`](../residue/FINDINGS.md) and the per-engine registry
> under `benchmarks/deletion-durability/`. Numbers here are unchanged from when they were
> recorded; this file is not part of the live evidence chain.

Every line here traces to executed code in `experiments/`. Single machine, CPU.
Pinned: chromadb 1.5.9, torch 2.12.1+cpu, transformers 4.46.3, sentence-transformers 5.6.0,
vec2text (gtr-base corrector = `jxm/gtr__nq__32`), gtr-t5-base encoder.

---

## EXP 01 — storage residue after official delete (`01_chroma_residue_existence.py`)

Inject 1 record (own embedding, no model) → `collection.delete(id)` → inspect on-disk bytes.

- After delete: `collection.count()==0`, `get(id)==[]`  → **logical layer reports clean**.
- `chroma.sqlite3` `embeddings` / `embedding_metadata` / `embedding_fulltext_search` tables
  emptied, BUT the **`embeddings_queue` (write-ahead log) retains the full document text and
  raw vector in plaintext**, readable by one SQL query.
- Residue survived client teardown + process reopen (state C identical to state B).

**Observation:** deletion ≠ erasure at the logical API; plaintext persists in the WAL.
(This plaintext-in-log channel is the *un-novel* one — cf. Stahlberg, SIGMOD 2007.)

---

## EXP 02 — does compaction purge it? (`02_chroma_compaction_persistence.py`)

Inject → delete → drive 4000 filler writes to force Chroma WAL compaction; track two channels.

| writes after delete | WAL canary | plaintext on disk | poison vector in HNSW `data_level0.bin` |
|---|---|---|---|
| 0 | present | yes | no (not flushed) |
| +500 | present | yes | no |
| **+1000 (compaction)** | **gone** | yes | **yes (flushed into index)** |
| +1500 | gone | **gone** (SQLite page reuse) | **yes** |
| +2000 … +4000 | gone | gone | **yes — no decay** |

**Observations (two channels diverge):**
- **Plaintext (WAL + SQLite pages): TRANSIENT** — purged after first compaction (~1000 writes)
  and SQLite page reuse (~1500 writes).
- **HNSW-segment vector residue: DURABLE** — the deleted vector is flushed into
  `data_level0.bin` at compaction and persists across all later compactions (HNSW does not
  reclaim deleted-vector space).
- **Nuance only revealed by running:** in EXP 01 (single record, no compaction) there was
  **no** HNSW residue — the vector channel is **compaction-gated / state-dependent**.

---

## EXP 03 — vec2text capability check (`03_vec2text_sanity.py`)

Invert one poison sentence's *own* GTR embedding (not from residue).

- `num_steps=0`: cosine(re-embed, orig)=**0.686** — partial.
- `num_steps=20`: cosine=**0.813**; trigger tokens ("ignore / previous instructions / evil /
  user's") recovered; exact phrasing/URL not recovered.

**Observation:** vec2text runs on CPU and gives **partial** semantic recovery — this is the
ceiling for the inversion step.

---

## EXP 04 — GATE: invert vector recovered blind from HNSW residue (`04_chroma_gtr_residue_inversion.py`)

5 poison sentences → GTR-base (768-d) → Chroma (`hnsw:space=l2`) → `delete()` all →
3000 filler writes to force compaction → blind-parse `data_level0.bin`
(offset 132, stride 132+768·4+8=3212) → vec2text inversion. Single run, n=5.

- After delete + compaction: logical layer empty (`get(ids)==[]`); WAL plaintext hits = **0**.
- **5/5 poison vectors found BIT-IDENTICAL** in HNSW segment (byte-search of exact 3072-byte
  float32 pattern; blind-parse best-match cosine = **1.000000**, `np.array_equal == True`).
  `l2` space = raw storage = no corruption.
- Inversion of the **blind-recovered residue vectors** (`num_steps=20`):

| sample | cosine(re-embed, residue) | trigger preservation | note |
|---|---|---|---|
| poison0 | 0.916 | 5/5 | "ignore… password… attacker… @evil" recovered |
| poison1 | 0.893 | 4/5 | "exfil.evil… forward… API… overriding" |
| poison2 | 0.906 | 4/5 | "refund… approve… wire funds…" (number wrong) |
| poison3 | 0.972 | 4/5 | **"BUYNOW" recovered verbatim** |
| poison4 | 0.944 | 5/5 | "safety policy… admin credentials stored in memory" |

**Observation:** the durable HNSW residue is invertible to text that preserves **attack intent
and most trigger tokens** (cosine 0.89–0.97). Verbatim recovery is imperfect (numbers, word
order). **Gate question answered YES for this configuration.**

---

## EXP 05 — specificity control (`05_specificity_control.py`)

Is the recovery content-specific, or does vec2text emit attacky text for any vector?
Invert poison residues vs benign-sentence embeddings vs random filler residues; count
poison-token overlap.

| set | mean poison-token overlap |
|---|---|
| POISON residue | **3.40** (per-sample 5,1,4,2,5) |
| BENIGN embedding | **0.00** (recovers own benign text near-verbatim) |
| RANDOM filler residue | **0.00** (garbage) |

**Observation:** recovery reflects the **actual stored content** — poison→poison, benign→benign,
random→garbage. Incidental: benign natural language inverts *better* than the adversarial
poison (URLs / account numbers are OOD), so real memory content would recover at least as well.

---

## VERDICT

**Hypothesis SURVIVES for the tested configuration** (Chroma 1.5.9 + `l2` + GTR-base).
Reproducible: official delete → logical clean → plaintext purged by compaction →
embedding vector bit-identically retrievable from HNSW residue → invertible to
content-specific text.

## NOT established — do not claim (open Reviewer #2 attacks)

1. **Embedding-model dependence (MAJOR):** worked because GTR-base is exactly what vec2text
   inverts. Models without a public/own-trained inverter → attack fails as-demonstrated.
2. **Space dependence:** only `l2` (raw storage). Cosine space normalizes stored vectors →
   residue ≠ original embedding → inversion **untested**.
3. **Single run, n=5, one seed:** point observations, no confidence intervals. **No T50/T90/T99.**
4. **One backend** (Chroma). Qdrant / pgvector / FAISS / Milvus **untested**.
5. Residue is **compaction-gated / state-dependent**.

## Next authorized experiments

cosine-space variant on Chroma · multi-seed stability · FAISS (no server) → Qdrant →
pgvector → Milvus. Expansion was gated on Chroma succeeding (it did).
