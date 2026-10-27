# MySQL: EXISTS over a derived EXCEPT ALL / INTERSECT ALL table loses duplicate rows

Status: found by a G\* pair (run A, pair 5732); reduced; not yet reported to MySQL. Draft report below.

## Smallest case

```sql
CREATE TABLE t0 (c0 INT);
CREATE TABLE t1 (c0 INT);
INSERT INTO t0 VALUES (7), (7);

SELECT COUNT(*)
FROM ((SELECT c0 FROM t0) EXCEPT ALL (SELECT c0 FROM t1)) AS a
WHERE EXISTS (SELECT 1 FROM t0 AS b WHERE a.c0 >= b.c0);
```

- Expected: 2. `t0 EXCEPT ALL t1` is the bag {7, 7} (t1 is empty), and both rows satisfy the EXISTS (7 ≥ 7).
- Actual: 1. `SELECT a.c0 …` with the same FROM and WHERE returns one row instead of two.
- The same with `(SELECT c0 FROM t0) INTERSECT ALL (SELECT c0 FROM t0)`: 1 instead of 2.

## Where it reproduces

| Version | EXCEPT ALL | INTERSECT ALL | with `optimizer_switch='duplicateweedout=off'` |
|---|---|---|---|
| 8.0.31 (first release with INTERSECT / EXCEPT) | 1 (wrong) | 1 (wrong) | 2 (right) |
| 8.0.46 | 1 (wrong) | 1 (wrong) | 2 (right) |
| 8.4.13 | 1 (wrong) | 1 (wrong) | 2 (right) |
| 9.4.0 | 1 (wrong) | 1 (wrong) | 2 (right) |
| 9.7.2 (LTS) | 1 (wrong) | 1 (wrong) | 2 (right) |
| 26.7.0 | 1 (wrong) | 1 (wrong) | 2 (right) |

So the bug has been present since INTERSECT ALL and EXCEPT ALL were added (8.0.31, October 2022). Official Docker images, default configuration; the same with `internal_tmp_mem_storage_engine` set to TempTable or MEMORY. Right answers from the reference evaluator (`gtrans/refeval.py`) and DuckDB 1.1.3 and 2.0.0.

## What changes the answer (MySQL 9.4.0)

| Variant | Result |
|---|---|
| as above | 1 (wrong) |
| no WHERE EXISTS | 2 |
| UNION ALL instead of EXCEPT ALL | 2 |
| `EXISTS (… WHERE a.c0 = b.c0)` | 2 |
| `EXISTS (SELECT 1 FROM t0 AS b)` (uncorrelated) | 2 |
| `a.c0 IN (SELECT b.c0 FROM t0 AS b)` | 2 |
| base table t0 instead of the derived EXCEPT ALL | 2 |
| `semijoin=off` or `duplicateweedout=off` | 2 |
| `firstmatch=off`, `loosescan=off`, `materialization=off`, `derived_merge=off`, `hash_set_operations=off` | 1 (wrong) |

Plan (EXPLAIN FORMAT=TREE, 9.4.0):

```
-> Aggregate: count(0)
    -> Remove duplicate a rows using temporary table (weedout)
        -> Filter: (a.c0 >= b.c0)
            -> Inner hash join (no condition)
                -> Table scan on a
                    -> Except all materialize
                        -> Table scan on t0
                        -> Table scan on t1
                -> Hash
                    -> Table scan on b
```

## Likely cause (a hypothesis, not checked in the source)

The semijoin is run with duplicate weedout over the derived table `a`. Weedout tells rows of `a` apart by their row position. The derived table of an EXCEPT ALL or INTERSECT ALL is materialized with a duplicate counter, so two equal output rows can share one position, and weedout then removes a genuine duplicate. UNION ALL materializes every row separately, which fits the table above. A verified report with the same mechanism but a different trigger exists: Bug #119225 "weedout not work for rematerialized temptable" (8.0.43, LATERAL derived table, extra rows instead of missing rows). We found no report of the EXCEPT ALL / INTERSECT ALL trigger (searches of bugs.mysql.com on 26 Oct 2026); the MySQL team should decide whether it is a duplicate.

## How the pair found it

- Gold query Q (simplified): `(SELECT … FROM (x) AS a WHERE EXISTS (…)) EXCEPT ALL (y)`, mutant Q′: `SELECT … FROM ((x) EXCEPT ALL (y)) AS a WHERE EXISTS (…)`, label =. The law L10 (a filter moves through the left side of EXCEPT ALL) made Q′ out of Q; five more law edits changed other places of the same pair (L10 in the other direction, L5 twice, L12, L15).
- Q gives 6 (right), Q′ gives 2 (wrong). Only Q′ has the trigger (EXISTS directly over the EXCEPT ALL derived table).
- The bug **loses** rows. A one-direction relation Q ⊑ Q′ with the bug on the Q side would still hold (a smaller Q stays inside Q′). The = from the law sees it in both directions.
- Neither ValScope's grammar (`compound_op ::= union | union all | intersect | except`) nor Pinolo's has INTERSECT ALL or EXCEPT ALL, so neither tool can emit the trigger as published. In our setup the two constructs cost two rows of T, and the laws L1, L2, L8, L9, L10 apply to them with no extra code.
- Not claimed: that other approaches (differential testing, TLP) could not find it if their generators emitted EXCEPT ALL under EXISTS.

## Draft for bugs.mysql.com (to be filed by the team)

Title: Semijoin with duplicate weedout drops duplicate rows of a derived EXCEPT ALL / INTERSECT ALL table

Description: the query above returns 1 instead of 2 on 8.0.31, 8.0.46, 8.4.13, 9.4.0, 9.7.2 and 26.7.0. Correct with duplicateweedout=off or semijoin=off. Correct when EXCEPT ALL is replaced by UNION ALL. Possibly related to Bug #119225 (weedout relies on row positions of a temporary table).
