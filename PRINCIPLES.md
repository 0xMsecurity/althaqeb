# Principles & Method

This is the charter for Althaqeb: how the project decides what to build, what to keep, and
what to discard. It governs *method*; [`STATE.md`](STATE.md) records the current state of
work and [`GRAVEYARD.md`](GRAVEYARD.md) records directions that have been ruled out.

The guiding commitment is simple. Reality is the only authority. Where a measurement and an
argument disagree, the measurement wins; where a result and a narrative disagree, the result
wins. Everything below follows from that.

## Purpose

Althaqeb aims to become a neutral, citable authority on a specific question: whether deletion
in AI memory systems is actually erasure. The work climbs a ladder, and each artifact is
expected to move at least one rung up it:

    research → experiments → tools → benchmarks → taxonomies → registries →
    reference implementations → standards → certification → authority

The current North Star, as ratified, is a neutral authority in AI security. A narrowing of that
domain to *erasure durability in AI memory systems* is under consideration and documented in
[`POSITIONING.md`](POSITIONING.md) §6; it is not yet ratified and is not assumed here.

## Truth hierarchy

When sources of evidence conflict, the higher level governs:

    nature → bytes → measurements → experiments → code → artifacts →
    papers → opinions → reasoning → narratives

Narratives are never protected against the levels above them.

## Evidence discipline

No result is invented — not a metric, timing, percentile, benchmark, success rate, novelty
claim, citation, or conclusion. Every quantitative claim traces to a committed result file, and
this is enforced mechanically rather than promised: the registry's build gate fails if any
published claim loses its evidence. Negative results are kept and reported; one real measurement
outweighs a great deal of argument.

## Standing adversarial review

Every major decision is examined through a fixed set of review lenses before it proceeds. No
single lens is allowed to dominate, and a decision must survive all of them. **Reality holds a
veto over every other lens** — if an experiment kills an idea, the idea dies immediately,
without appeal to sunk cost.

- **Reviewer #2** — assumes every claim is wrong and looks for the fatal flaw early: novelty,
  methodology, statistics, assumptions, terminology, evaluation, reproducibility, and whether a
  "first" is actually true or the work is merely engineering.
- **Adversary** — assumes attackers are at least as capable as the defender: how a control is
  bypassed, hidden from, or poisoned; how the benchmark or the tool itself is gamed.
- **Scientist** — lets nature decide: has this been measured or guessed; is it reproducible; what
  would falsify it; one trajectory is not a statistic, and unknown means unknown.
- **Engineer** — judges whether it runs: deterministic, resource-bounded, tested, version-pinned,
  regression-covered, with chain of custody. Working systems over elegant designs that do not run.
- **DFIR** — judges whether the evidence can be trusted: read-only, sound acquisition,
  reproducible findings, no contamination.
- **Statistics** — guards against self-deception: precision and recall over raw accuracy under
  imbalance, confidence intervals, correction for multiple comparisons, attention to base rates.
- **Product** — asks whether the work builds a compounding asset (data, formats, tooling,
  standards) rather than a one-off feature.
- **CEO** — asks whether it still matters in one, three, and five years, and whether it builds
  leverage, moats, reputation, or authority.
- **Company** — gives internal functions a voice — research, engineering, security, QA, legal,
  scope, narrative, cost, support, direction — so that no single concern decides alone.
- **Ethics** — weighs dual-use, privacy, disclosure obligations, and potential for harm before
  declaring success.
- **Academic** — holds claims to publishable standards: exact delta over prior work, required
  baselines, no casual "first."
- **Commercial** — asks how the work could sustain itself: assessment, certification, incident
  response, training, or premium tooling around a free neutral core.
- **Authority** — asks whether the field would cite Althaqeb before its alternatives.
- **Reality** — the final authority. Nature decides, not vision, ego, papers, or hype.

What survives this process is the process itself. Ideas, products, papers, and tools all
eventually die; the review is what persists.

## Continuous destruction

Hostile review is permanent, not a phase. Novelty, assumptions, statistics, threat model,
engineering, ethics, reproducibility, practicality, economics, maintenance, and market relevance
are all fair targets. When evidence kills a branch, it is killed at once and recorded in
[`GRAVEYARD.md`](GRAVEYARD.md).

## No sunk cost

Nothing is sacred — not architectures, hypotheses, papers, repositories, months of work, or
names. When reality contradicts a commitment, the commitment yields.

## Compounding assets

Each action should strengthen at least one durable asset: knowledge, code, benchmarks, corpora,
taxonomies, registries, reference implementations, documentation, standards, relationships,
reputation, or authority. Work that builds none of these is questioned before it continues.

## Resource allocation

A rough budget keeps effort proportionate, weighted toward building and measuring rather than
deliberating or polishing:

- 40% implementation
- 25% experiments
- 15% destruction (adversarial review)
- 10% tooling
- 10% documentation

## Engineering and scientific standards

Engineering aims for determinism, reproducibility, chain of custody, self-tests, version pinning,
containerization, artifact-evaluation quality, maintainability, and one-year survivability —
systems, not demos. Science destroys novelty claims before trusting them, reproduces before
extending, compares against adjacent fields, distinguishes the work from prior art, and never
claims "first" casually. Negative results are publishable.

## Saturation

When repeated attacks stop changing the conclusion, the work on that question is done. The
response is not to manufacture more of it but to ask which larger layer should emerge next, and
to move up the ladder:

    finding → tool → benchmark → registry → standard → certification → authority

## Scope awareness

The project tracks the wider landscape — agent-memory security, vector-database security, MCP
security, tool poisoning, agent runtimes, multi-agent systems, RAG security, embedding leakage,
model supply chain, agent identity, AI incident response and forensics, benchmarks, taxonomies,
standards, and certification — and maps relationships between them, while avoiding capture by any
single sub-area.

## Current pillar

The surviving line of work is **persistent vector residue after logical deletion**, with
`vdbresidue` as its headline asset. ChromaDB exhibits architectural residue via the hnswlib
`DELETE_MARK`; most other engines reclaim it through garbage collection. The evidence is real and
has survived repeated attack. The pillar is maintained without letting the project narrow into a
single backend or become defined by one vendor.
