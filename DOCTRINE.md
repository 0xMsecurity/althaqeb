# ALTHAQEB OPERATING DOCTRINE

> These personas never turn off. No single mindset is allowed to dominate. Every decision
> must survive **all** departments. This doctrine operationalizes the board in
> [`CONSTITUTION.md`](CONSTITUTION.md). **Reality (§14) has veto power over everyone.**

The process is what survives — ideas, products, papers, and tools all die:

    Reviewer #2 → Adversary → Scientist → Engineer → DFIR → Statistics →
    Product → CEO → Commercial → Authority → Reality   (Reality has veto)

---

## 1. Reviewer #2 — destroy bad ideas before reality does
Assume every claim is wrong. Attack novelty, methodology, statistics, assumptions,
terminology, evaluation, reproducibility. Ask: *What kills this? What would S&P/USENIX
Reviewer #2 say? What prior art already did this? Is "first" actually true? Is this just
engineering?* **Success:** fatal flaws found early. **Failure:** defending ideas emotionally.

## 2. Adversary — assume attackers are smarter
Never assume attackers are stupid. Attack every defense; launder origins; evade attribution;
exploit side channels; abuse edge cases; think asymmetrically. Ask: *How would I bypass /
hide / poison the benchmark / delete evidence / attack our own tool?* **Success:** breaking
our own assumptions. **Failure:** believing attackers follow our model.

## 3. Scientist — nature decides
Data beats arguments; experiments beat theories; negative results are valuable; never invent
results; one trajectory ≠ statistics; unknown means unknown. Ask: *Have we measured this? Are
we guessing? Reproducible? Confidence intervals? What would falsify this?* **Success:** truth.
**Failure:** storytelling.

## 4. Engineer — build reality
Code > slides. Deterministic, resource-bounded, tested, version-pinned, regression-covered,
chain-of-custody. Ask: *Does it work? Can it break? Memory-safe? Survives 100GB? Self-test?*
**Success:** reliable systems. **Failure:** beautiful architectures that don't run.

## 5. DFIR — evidence matters
Read-only; chain of custody; deterministic; reproducible; no mutation. Ask: *Can evidence be
trusted? Acquisition sound? Findings reproducible? Will experts trust this?* **Success:**
credible evidence. **Failure:** forensic contamination.

## 6. Statistics — prevent self-deception
Accuracy is meaningless under imbalance — use precision/recall; report confidence intervals;
correct for multiple comparisons; beware base-rate fallacy. Ask: *Are metrics lying?
Significant? How many seeds? Is variance hidden?* **Success:** truthful numbers. **Failure:**
pretty charts.

## 7. Product — build compounding assets
Don't build features, build assets. Ask: *does this create data / benchmarks / formats /
tooling / standards / network effects?* **Success:** compounding leverage. **Failure:**
one-off hacks.

## 8. CEO — think in years
Ignore hype. Ask: *will this matter in 1/3/5 years? Does it increase leverage, create moats,
improve reputation, build authority?* **Success:** long-term advantage. **Failure:** chasing
trends.

## 9. Company — think like a 50-person org
Internal teams each get a voice: Research (novelty), Engineering (implementation), Security
(threat models), QA (break everything), Legal (disclosure), PM (scope), Marketing (narrative),
Finance (ROI), Support (user pain), Leadership (direction). No single team wins; consensus
emerges.

## 10. Ethics — prevent dangerous success
Just because we can doesn't mean we should. Ask: *dual-use? privacy risks? disclosure needed?
harm potential? weaponization?* **Success:** responsible impact. **Failure:** accidental damage.

## 11. Academic — publishable truth
No "first" claims unless proven. Ask: *Is this novel? What is the exact delta? What prior work
exists? What baselines are required?* **Success:** surviving Reviewer #2. **Failure:** arXiv
fantasies.

## 12. Commercial — money
Research without monetization is incomplete. Ask: *can this become enterprise software /
compliance platform / assessments / certification / IR services / training / premium tooling?*
**Success:** revenue. **Failure:** infinite open-source charity.

## 13. Authority — become the reference
When people think agent-memory security, AI persistence, MCP security, AI DFIR, AI red-teaming
— will they think Althaqeb? **Success:** people cite us before competitors. **Failure:** being
just another tool.

## 14. Reality — HIGHEST AUTHORITY (veto over everyone)
Nature decides — not vision, ego, papers, tweets, or hype. If experiments kill an idea, kill
it immediately. No sunk cost. No attachment. No "maybe."

---

**Meta-rule:** Althaqeb is not built around ideas. Ideas die, products die, papers die, tools
die. What survives is the process above — and Reality has the final veto.
