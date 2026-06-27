# Early-exploration archive (EXP 01–05)

The first five exploratory experiments and their raw-observation log, kept verbatim for
provenance. They predate the structured, evidence-gated work under
[`../residue/`](../residue/) and the per-engine registry in
[`../../benchmarks/deletion-durability/`](../../benchmarks/deletion-durability/).

These scripts are **not** part of the live evidence chain and are not cited by the
registry; they are retained so the project's history is auditable end to end.

| File | What it explored |
|---|---|
| `01_chroma_residue_existence.py` | Storage residue after an official `delete()` |
| `02_chroma_compaction_persistence.py` | Whether compaction purges the residue |
| `03_vec2text_sanity.py` | vec2text inversion capability check |
| `04_chroma_gtr_residue_inversion.py` | Inverting a vector recovered blind from HNSW residue |
| `05_specificity_control.py` | Specificity control (poison vs benign vs random) |
| `RESULTS.md` | Raw-observation log for EXP 01–05 |

Current record: [`../residue/FINDINGS.md`](../residue/FINDINGS.md).
