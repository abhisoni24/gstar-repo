# G and T for MySQL (from ValScope's grammar)

Source grammar: `documents/pinolo_extension_bnf.md` of the ValScope repository (commit e158a9d in the connected folder). `make_inputs.py` writes `grammar.json` (G, 110 productions) and `table_T.json` (T, 51 operator rows, 15 laws with 89 instances); `table_T.md` shows T in the note's layout.

## What G covers

Every table t0, t1, t2 has the schema (c0 INT, c1 INT, c2 VARCHAR(8)), nullable, duplicates allowed. Every row query returns c0, c1, c2, so set operations are always union-compatible. Three statement families:

| family | statement | relation checked |
|---|---|---|
| rows | a row query Q | bag inclusion or bag equality |
| value | `SELECT agg(a.c0) [+ k …] FROM (Q) AS a` | value order, NULL as the least value |
| groups | `SELECT a.c1, COUNT(*) FROM (Q) AS a GROUP BY a.c1 HAVING H` | bag inclusion or equality |

| ValScope BNF construct | in G | note |
|---|---|---|
| query_spec, DISTINCT | yes | `SELECT [DISTINCT] a.c0, a.c1, a.c2 FROM … WHERE …` |
| table_ref: table, derived table | yes | `t AS a`, `(Q) AS a` |
| joined_table INNER / LEFT / RIGHT with ON | yes | two operands, base tables or derived tables; projects a.* |
| CROSS JOIN | no | in MySQL it is the same as INNER JOIN |
| WHERE | yes | |
| GROUP BY / HAVING | yes | one grouping column; HAVING over aggregates |
| ORDER BY, LIMIT | no | order is irrelevant for bags; LIMIT without a total order is nondeterministic (assumption A2) |
| WITH (CTE), FOR UPDATE | no | CTE needs context (assumption A3); locking does not change results |
| comparison =, <>, <, >, <=, >= | yes | column vs constant, column vs column |
| BETWEEN | yes | three slots: value, low, high |
| IS [NOT] NULL, TRUE / FALSE | yes | |
| AND, OR, NOT | yes | |
| EXISTS (subquery) | yes | correlated, one level: `EXISTS (SELECT 1 FROM t AS b WHERE …a…b…)` |
| LIKE, REGEXP, RLIKE | no | T has no order on patterns yet |
| UNION, UNION ALL, INTERSECT, EXCEPT | yes | plus INTERSECT ALL and EXCEPT ALL (MySQL 8.0.31+), not in ValScope |
| aggregates COUNT, COUNT(DISTINCT), COUNT(*), SUM, MIN, MAX, AVG | yes | STDDEV / VAR no |
| function calls, CASE, CAST, scalar subqueries | no | |
| arithmetic | partly | `+ k` (k ≥ 0) on an aggregate value |

## Facts in T that differ from a set / two-valued reading

- Truth order FALSE < UNKNOWN < TRUE. AND, OR, WHERE are monotone and NOT is antitone in it; `x θ k` is UNKNOWN for NULL x whatever k, so comparison signs stand, and `NOT (x < k) = x ≥ k` still holds.
- UNION (distinct) has no identity and no bound under bags: `x UNION ∅` is `DISTINCT x`, not x. So `x ⇒ x UNION z` and `x UNION y ⇒ x` are not generated.
- EXCEPT (distinct) is deflationary in its left slot: `x EXCEPT y ⊑ DISTINCT x ⊑ x`. So `x EXCEPT y ⇒ x` (ValScope's FixMExcept) is generated as a drop justified by a bound, not by an identity.
- LEFT / RIGHT JOIN: the ON slot has sign 0. A new match removes the NULL-extended row of an outer row, so neither direction is guaranteed once the select list or WHERE reads the inner side. Only INNER JOIN's ON slot is monotone.
- Scalar aggregates use the order "NULL is least". MAX and the COUNTs are monotone in their input; MIN, AVG and SUM have sign 0 (MIN of an empty input is NULL, the least value, while MIN of a non-empty input can only fall as rows are added; SUM can fall with negative values). The order MIN ≼ AVG ≼ MAX holds on every input, empty included.
- Inside HAVING every group is non-empty, so MIN, AVG and MAX are NULL together and MIN ≼ AVG ≼ MAX; `COUNT(DISTINCT c) ≼ COUNT(c) ≼ COUNT(*)`.
- The grouped statement has sign 0 in its input query: changing the input changes the groups' values, not just which groups appear.

## Laws (all linear, valid under bags and three-valued logic)

L1 commutativity and L2 associativity (UNION, UNION ALL, INTERSECT, INTERSECT ALL, AND, OR), L3 NOT NOT, L4 De Morgan, L5 negated comparison and `NOT (x IS NULL) = x IS NOT NULL`, L6 filter merge, L7 filter swap, L8 `(x EXCEPT y) EXCEPT z = x EXCEPT (y UNION z)` and its ALL form, L9 difference swap, L10 a filter through EXCEPT / INTERSECT (both forms), L11 ON / WHERE exchange and L12 ON merge for INNER JOIN, L13 `SELECT DISTINCT … FROM (x UNION ALL y) WHERE TRUE = x UNION y`, L14 derived-table merge, L15 `WHERE TRUE` removal.
