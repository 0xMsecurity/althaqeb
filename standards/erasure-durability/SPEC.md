# VEDC — Vector-store Erasure-Durability Classification

- **Status:** DRAFT v0.1 (provisional; subject to revision as evidence grows)
- **Editor:** Althaqeb
- **Reference data:** [`benchmarks/deletion-durability/registry.json`](../../benchmarks/deletion-durability/registry.json)
- **Conformance tool:** [`classify.py`](classify.py) → [`CLASSIFICATION.md`](CLASSIFICATION.md)

> This is a classification framework, not a vendor scorecard. It assigns each storage engine
> a class describing **how long a logically-deleted embedding vector remains physically
> recoverable on disk**, and a confidence level reflecting how well-replicated that
> classification is. Every classification must trace to committed, positive-control-validated
> measurements. Reality has veto: a class is only as good as its evidence.

---

## 1. Motivation

When an application calls `delete()` on a vector and the engine reports the logical layer
clean, that is **not** equivalent to the bytes being gone. For "right to be forgotten"
(GDPR Art. 17 / CCPA) and incident response, the operationally relevant question is: *after a
successful delete, for how long can the embedding vector still be reconstructed from disk?*
VEDC standardizes the answer.

## 2. Scope

In scope: on-disk persistence of the *embedding vector* (and, where applicable, its
invertibility back to text) after a logical `delete()`, and the maintenance operation (if
any) that physically reclaims it. Out of scope: network interception, memory scraping, backups,
replication logs, and access-control bypass — these are real but orthogonal channels.

## 3. Normative terminology

- **Logical deletion** — the engine's official `delete()` returns success and the record no
  longer appears in queries.
- **Residue** — an embedding vector that remains byte-recoverable from the on-disk store
  after logical deletion. Detected as bit-identical bytes OR cosine > 0.999 to the original.
- **Recovery window** — the interval between logical deletion and the first reclamation pass
  that purges the residue. May be unbounded.
- **Reclamation pass** — an engine operation (compaction-GC, vacuum, optimizer, tombstone
  cleanup, table rewrite) that physically removes the residue.
- **Positive control** — a vector known to be *live* (not deleted) that the detection method
  MUST find present at every checkpoint. If the positive control is ever absent, the
  measurement is INVALID (the scan is not working) and MUST be discarded.
- **Self-identifying deletion** — the on-disk format records *which* records were deleted
  (e.g. an hnswlib `DELETE_MARK` bit, a delta-log tombstone, a heap `xmax`), so an analyst
  can target exactly the deleted residue without the original IDs.

## 4. Normative measurement method

A conformant measurement MUST:

1. **Acquire read-only.** The store is never mutated by the measurement (DFIR requirement).
2. **Use byte-exact or high-cosine detection.** Presence = bit-identical float32 bytes, or
   cosine > 0.999 via a sliding `float32[dim]` window (covers raw and L2-normalized storage).
3. **Include a live positive control** at every checkpoint (§3). Invalid runs are discarded.
4. **Checkpoint the lifecycle:** before delete → after delete → after each reclamation pass
   the engine offers (vacuum / compaction-GC / optimizer / cleanup / full rewrite).
5. **Disclose maintenance configuration** (e.g. autovacuum on/off, GC interval, compaction
   thresholds), because the window depends on it.
6. **Emit a committed machine-readable result file**; the registry entry MUST cite it. The
   build gate (`build_matrix.py`) fails if the cited evidence is absent.

## 5. Classes

| Class | Name | Definition |
|---|---|---|
| **VEDC-U** | Unbounded | Residue persists; no reclamation pass observed under any tested pressure (writes, restarts, drop, idle, reclaim attacks). |
| **VEDC-AU** | Auto / untimed | An automatic pass (optimizer, autovacuum) purges it, but no purge *time* was measured. |
| **VEDC-AT** | Auto / timed | An automatic background pass purges it and a purge time WAS measured. |
| **VEDC-M** | Manual-only | Only an explicit operator command (e.g. `VACUUM FULL`, table rewrite) purges it. |
| **VEDC-N** | None | No residue — the engine reclaims at write/close (validated by positive control passing on a clean store). |

A class MAY carry the **`+S`** suffix (e.g. `VEDC-U+S`) when deletion is self-identifying (§3),
because that materially increases practical recoverability (an analyst inverts the few deleted
vectors, not the whole store).

### Conformance levels (Statistics requirement)

- **Confirmed** — the SAME measurement repeated across ≥3 seeds OR across engine versions,
  with a passing positive control and committed evidence. (Multiple delete-ratio / timing
  *conditions* measure different things; they strengthen a result but do NOT by themselves
  confer Confirmed.)
- **Provisional** — a single trajectory (n=1 seed) with a passing positive control and
  committed evidence — even if several conditions were tested. Honest default until the
  measurement is repeated across seeds/versions. This is the current state of every engine
  except ChromaDB; multi-seed replication is the next experiment.
- **Unverified** — no committed evidence. MUST NOT be published as a classification.

## 6. Claiming a classification (anti-gaming — Adversary requirement)

A classification claim is only admissible if:

- it cites a committed result file that the build gate can verify exists;
- that result includes a **passing positive control** (this is what prevents a vendor from
  claiming `VEDC-N` by simply pointing a weak scanner at the store — the control proves the
  scan *would* have found a present vector);
- the detection is byte-exact / high-cosine (not a semantic similarity hand-wave);
- the measurement is reproducible from the cited script + pinned environment.

Threats this resists: cherry-picked checkpoints (lifecycle checkpoints are mandatory),
disabled-scanner false negatives (positive control), and "we deleted it" assertions with no
byte-level proof (byte-exact detection + blind parse).

## 7. Relation to prior work (Academic requirement — exact delta)

The underlying phenomenon — that logically deleted database records persist physically until a
reclamation pass — is **well established and NOT claimed as novel here**: Stahlberg et al.,
*Threats to Privacy in the Forensic Analysis of Database Systems* (SIGMOD 2007); the secure-
deletion literature (e.g. Reardon et al., *SoK: Secure Data Deletion*, IEEE S&P 2013); and GDPR
Art. 17. We are not aware of a prior **cross-engine, evidence-traceable classification of
deletion durability specifically for vector stores**, nor of the specific finding that the
residue is (a) an *embedding vector invertible back to text* and (b) **unbounded on ChromaDB**
while bounded on every other engine measured. Those are the contributions; the persistence
phenomenon itself is prior art. No "first" is claimed beyond this delta.

## 8. Ethics & disclosure (Ethics requirement)

This method is **dual-use**: it verifies GDPR erasure (defensive) and also recovers
"deleted" sensitive vectors (offensive). VEDC is framed for the defensive case —
erasure verification and DFIR. Engine-specific findings are handled under coordinated
disclosure (see [`experiments/residue/disclosure/`](../../experiments/residue/disclosure/));
classifications are published only at honest, non-sensational severity.

## 9. Versioning

VEDC is versioned with the registry. Breaking changes to classes or method bump the minor
version. Each published `CLASSIFICATION.md` records the registry version it was generated from.
