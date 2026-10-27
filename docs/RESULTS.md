# GTrans on MySQL with ValScope's grammar: results (26 Oct 2026)

## 1. What was built

| Item | Size | File |
|---|---|---|
| G: the core of ValScope's SQL grammar that fits our assumptions (no CTE, no LIMIT, no LIKE / CASE / functions); adds INTERSECT ALL and EXCEPT ALL | 110 productions, 16 non-terminals | `inputs/mysql/grammar.json`, mapping in `inputs/mysql/README_mysql.md` |
| T for MySQL (bags, NULLs, 3VL FALSE < UNKNOWN < TRUE) | 51 operator rows, 15 linear laws (89 instances), extremes TRUE / FALSE | `inputs/mysql/table_T.json`, readable form `table_T.md` |
| G\* = GTrans(G, T) | 4,294 rules over 41 labelled non-terminals | `outputs/mysql/Gstar.txt`, `Gstar.json`, `Gstar_summary.md` |

Rules of G\* by node kind: copy 688, swap 674, insert 69, drop 69, extreme 12, constant 4, law 2,778.

Three statement families: rows (`Q`, checked as bag inclusion or equality), value (`SELECT agg(a.c0) [+ k] FROM (Q) AS a`, NULL is the least value), groups (`… GROUP BY a.c1 HAVING H`).

## 2. How we measured "relations they do not cover"

We compare three generators that share G, T and the sampler, and differ only in which rules of G\* they may use:

- **G\*:** all rules.
- **G\*_V:** ValScope's inventory (each of its 26 mutators mapped to the G\* edits it makes), one edit per pair, only at places its mutators touch, no laws, no =.
- **G\*_P:** Pinolo's inventory (its Table 1), several edits allowed but none inside another changed node, no laws, no =.

**M1, edit inventory.** Every edit type in G\* is mapped by hand to the mutator that makes it, if any.
*Example.* `swap: AND ⇒ OR` (from the order AND ≼ OR in T) is in neither list. ValScope has "a AND b AND c ⇒ a AND b" (a drop), Pinolo has "p ⇒ TRUE".

**M2, pair-shape coverage.** An atom is (edit, polarity at the edit, kinds of context above it: NOT, EXCEPT-right, EXISTS, aggregate, HAVING, ON, derived table, set operation, join operand, arithmetic, grouped input). Counted exactly for each generator, by propagating contexts through its rules (no sampling).
*Example.* (swap AND ⇒ OR, polarity −, under NOT): `WHERE NOT (c0 > 3 AND c1 < 5)` ⇒ `WHERE NOT (c0 > 3 OR c1 < 5)`, the result can only shrink, label ↓.

**M3, out of reach.** For each pair sampled from G\*: could ValScope (one edit from its inventory at an allowed place) or Pinolo (its edits, none nested, no equalities, row queries only) make this pair from the same gold query? Reported with their grammar limits.
*Example.* The pair that found the MySQL bug below has six law edits and label =, so neither tool can make it.

### Results (`outputs/mysql/measures/`, 20,000 sampled pairs per generator, depth ≤ 5)

| Measure | G\* | G\*\_V | G\*\_P |
|---|---|---|---|
| M1 edit types | 362 | 70 mapped | 100 mapped |
| M1 edit types in neither list | 240 (all 162 laws, 38 swaps, 21 inserts, 19 drops) | | |
| M2 exact atoms | 71,774 | 9,068 | 20,106 |
| M2 atoms only in G\* | 51,039 (71%) | | |
| same, mirror images merged (dropping the left or the right operand of a commutative operator counts once) | 48,819; without laws 3,999 | | |
| M2 distinct sampled shapes | 7,218 | 390 | 1,793 |
| pairs with ≥ 2 edits | 64% | 0% | 20% |
| pairs with an edit under negative polarity | 11.7% | 9.1% | 4.3% |

G\*\_V and G\*\_P atoms are subsets of G\* atoms (checked).

| M3: share of G\* pairs out of reach of both tools (with their grammar limits) | |
|---|---|
| all pairs | 90.4% |
| pairs without a law | 52.2% |
| pairs with exactly one edit | 76.3% |

Why not ValScope (all pairs): more than one edit 12,797; equivalence (law) 4,665; edit not in its inventory or not at an allowed place 1,858; construct outside its grammar 19. Why not Pinolo: equivalence 15,998; edit not in its inventory 2,226; edit inside a changed node 206; construct outside its grammar 129.

How to read these numbers: most of the gain comes from equalities (laws) and from composing several edits in one pair. Even without laws, about half of the pairs are out of reach. M2 is syntactic, so the mirror-merged count is the conservative one.

## 3. Running the pairs

Every statement was also run by a reference evaluator written from the SQL / MySQL semantics (`gtrans/refeval.py`: bags, NULLs, 3VL, joins, set operations, correlated EXISTS, grouping, aggregates). It decides who is right when the relation fails.

| Run | Pairs | DBs | Engines | Pair executions per engine | Relation broken (engine) | Relation broken (reference) |
|---|---|---|---|---|---|---|
| A | 20,000 from G\*, depth ≤ 6 | 10 | MySQL 9.4.0, 26.7.0; DuckDB 1.1.3 | 200,000 | MySQL 1 pair; DuckDB 7 pairs | 0 |
| B | 10,000 each from G\*, G\*\_V, G\*\_P, depth ≤ 6 | 10 | MySQL 8.0.46, 8.4.13, 9.4.0, 9.7.2, 26.7.0; DuckDB 2.0.0 | 300,000 | 0 | 0 |
| C | 30,000 from G\*, depth ≤ 7 | 10 | MySQL 8.4.13, 9.7.2, 26.7.0 | 300,000 | 0 | 0 |

Databases: three tables (c0 INT, c1 INT, c2 VARCHAR(8)), up to 8 rows each, 15% NULLs, duplicate rows.

**Soundness.** The reference never broke a relation: 0 of 600,000 (pair, database) evaluations in runs B and C, and 0 among the 37 violations of run A. So no false alarm came from T.

**Reference checked against the engines.** After one fix, the reference agreed with all five MySQL versions on every query of runs B and C (about 4.8 million query executions). The fix: the first pass of run B showed 37 disagreements, all the same for every MySQL version, all on a RIGHT JOIN whose right side yields all-NULL rows. The reference was wrong (it confused such a row with its own NULL-extension marker); fixed, with a regression test (`tests/test_mysql.py`), and run B repeated.

## 4. Findings

| # | System | What | Status |
|---|---|---|---|
| 1 | MySQL 8.0.31 to 26.7.0 | A correlated EXISTS over a derived EXCEPT ALL or INTERSECT ALL table loses duplicate rows (semijoin duplicate weedout). Smallest case: t0 = {7, 7}, t1 empty, `SELECT COUNT(*) FROM ((SELECT c0 FROM t0) EXCEPT ALL (SELECT c0 FROM t1)) AS a WHERE EXISTS (SELECT 1 FROM t0 AS b WHERE a.c0 >= b.c0)` returns 1, should be 2. | **Candidate new bug.** Not found on bugs.mysql.com; same mechanism as verified Bug #119225 (different trigger and symptom). Not reported yet. Details: `BUG_mysql_except_all_weedout.md` |
| 2 | DuckDB 2.0.0 | `SUM` over a LEFT JOIN whose right side matches nothing gets wrong statistics; `HAVING SUM(x) <= 1` is folded to TRUE. | **Known**, open issue duckdb/duckdb#27641 (21 Oct 2026). Rediscovered in run B (once by G\*, once by G\*\_V); the relation did not see it, the reference did |
| 3 | DuckDB 1.1.0 to 1.4.5 (Python API) | `(SELECT x FROM u) UNION ALL ((SELECT x FROM u) UNION ALL (SELECT x FROM v))` misses the last branch's rows | **Fixed upstream** (correct in 1.0.0 and from 1.5.0). Run A, 6 pairs |
| 4 | DuckDB 1.0.0 to 1.1.3 | filter over a derived table: `… (SELECT … WHERE c1 > c0) WHERE NOT (c1 <> 9) AND c0 >= 9` returns a row with c1 = 12 | **Fixed upstream** (correct from 1.2.0). Run A, 1 pair |

How bug 1 was found: Q = `(SELECT … FROM (x) AS a WHERE EXISTS (…)) EXCEPT ALL (y)`, Q′ = `SELECT … FROM ((x) EXCEPT ALL (y)) AS a WHERE EXISTS (…)` (law L10, filter through the left side of EXCEPT ALL), plus five more law edits; label =. MySQL gave 6 for Q (right) and 2 for Q′ (wrong). Two points matter for the paper:

- The bug **loses** rows. If the buggy query had been the smaller side of a ⊑ pair, the relation would still hold. The = from the law observes it.
- The trigger needs EXCEPT ALL or INTERSECT ALL, which neither ValScope's nor Pinolo's grammar has. In our setup they cost two rows of T, and five laws then applied to them with no new code. We do not claim that differential testing or TLP could not find it if their generators produced these constructs.

## 5. Limits of these results

- G\*\_V and G\*\_P are ablations inside our framework, not runs of ValScope and Pinolo. The mapping of their mutators to G\* edits is by hand (`scripts/measure_gain.py`, functions `valscope_mutator` and `pinolo_mutator`), from ValScope's 26 mutators and Pinolo's Table 1; Pinolo's full online list was not checked.
- Bug-finding at these budgets is rare: one MySQL bug in 2.8 million pair executions. In runs B and C, 296 sampled pairs had the trigger shape of bug 1 but none provoked it (it also needs duplicates, a non-equality correlation and the optimizer's choice of weedout). A fair bug-finding comparison needs the 24 h protocol of `EXPERIMENT_PLAN.md`.
- G covers a core of ValScope's grammar, not all of it (no CTE, LIMIT, LIKE, CASE, functions, IN).
- The reference evaluator is trusted only after the differential check above; it does not model MySQL's type coercions or collations beyond the lowercase strings used here.
