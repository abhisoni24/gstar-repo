# Table T for mysql

T for MySQL 9.x: bags, three-valued logic (FALSE < UNKNOWN < TRUE), NULLs in data. signs: one per slot; identity: greatest / least per slot; bound: f(x, ·) ⊑ x (deflationary) or x ⊑ f(x, ·) (inflationary) for x in that slot; order: codes Ci.j; laws: ids. Written by make_inputs.py.

| operator | signs (α, β, γ, δ) | identity: greatest | identity: least | bound | order | L1 | L2 | L3 | L4 | L5 | L6 | L7 | L8 | L9 | L10 | L11 | L12 | L13 | L14 | L15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WRAP | + |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TBL | 0 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  | ✓ | ✓ |
| SEL | 0, + |  |  |  | C1.2 |  |  |  |  |  | ✓ | ✓ |  |  |  |  |  |  | ✓ | ✓ |
| SELD | 0, + |  |  |  | C1.1 |  |  |  |  |  |  |  |  |  |  |  |  |  | ✓ |  |
| DSEL | +, + | β: TRUE |  | α: deflationary | C2.2 |  |  |  |  |  | ✓ | ✓ |  |  | ✓ |  |  |  | ✓ |  |
| DSELD | +, + |  |  | α: deflationary | C2.1 |  |  |  |  |  |  |  |  |  |  |  |  | ✓ | ✓ |  |
| JSEL_INNER | 0, 0, +, + |  |  |  | C3.1, C4.1 |  |  |  |  |  |  |  |  |  |  | ✓ | ✓ |  |  |  |
| JSEL_LEFT | 0, 0, 0, + |  |  |  | C3.2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| JSEL_RIGHT | 0, 0, 0, + |  |  |  | C4.2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| JDSEL_INNER | +, +, +, + |  |  |  | C5.1, C6.1 |  |  |  |  |  |  |  |  |  |  | ✓ | ✓ |  |  |  |
| JDSEL_LEFT | +, 0, 0, + |  |  |  | C5.2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| JDSEL_RIGHT | 0, +, 0, + |  |  |  | C6.2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| UNION | +, + |  |  |  | C8.2, C10.2 | ✓ | ✓ |  |  |  |  |  | ✓ |  |  |  |  | ✓ |  |  |
| UNION_ALL | +, + |  | α: EMPTY, β: EMPTY |  | C7.3, C8.3, C9.3 | ✓ | ✓ |  |  |  |  |  | ✓ |  |  |  |  | ✓ |  |  |
| INTERSECT | +, + |  |  | α: deflationary, β: deflationary | C7.1, C8.1 | ✓ | ✓ |  |  |  |  |  |  |  | ✓ |  |  |  |  |  |
| INTERSECT_ALL | +, + |  |  | α: deflationary, β: deflationary | C7.2 | ✓ | ✓ |  |  |  |  |  |  |  | ✓ |  |  |  |  |  |
| EXCEPT | +, - |  |  | α: deflationary | C9.1, C10.1 |  |  |  |  |  |  |  | ✓ | ✓ | ✓ |  |  |  |  |  |
| EXCEPT_ALL | +, - |  | β: EMPTY |  | C9.2 |  |  |  |  |  |  |  | ✓ | ✓ | ✓ |  |  |  |  |  |
| TRUE | (leaf) |  |  |  | C11.2 |  |  |  |  |  |  |  |  |  |  |  | ✓ | ✓ |  | ✓ |
| FALSE | (leaf) |  |  |  | C11.1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| AND | +, + | α: TRUE, β: TRUE |  |  | C12.1 | ✓ | ✓ |  | ✓ |  | ✓ |  |  |  |  |  | ✓ |  |  |  |
| OR | +, + |  | α: FALSE, β: FALSE |  | C12.2 | ✓ | ✓ |  | ✓ |  |  |  |  |  |  |  |  |  |  |  |
| NOT | - |  |  |  |  |  |  | ✓ | ✓ | ✓ |  |  |  |  |  |  |  |  |  |  |
| < | -, + |  |  |  | C13.1, C17.1 |  |  |  |  | ✓ |  |  |  |  |  |  |  |  |  |  |
| <= | -, + |  |  |  | C13.2, C14.2 |  |  |  |  | ✓ |  |  |  |  |  |  |  |  |  |  |
| = | 0, 0 |  |  |  | C14.1, C15.1 |  |  |  |  | ✓ |  |  |  |  |  |  |  |  |  |  |
| >= | +, - |  |  |  | C15.2, C16.2 |  |  |  |  | ✓ |  |  |  |  |  |  |  |  |  |  |
| > | +, - |  |  |  | C16.1, C18.1 |  |  |  |  | ✓ |  |  |  |  |  |  |  |  |  |  |
| <> | 0, 0 |  |  |  | C17.2, C18.2 |  |  |  |  | ✓ |  |  |  |  |  |  |  |  |  |  |
| BETWEEN | 0, -, + |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ISNULL | 0 |  |  |  |  |  |  |  |  | ✓ |  |  |  |  |  |  |  |  |  |  |
| ISNOTNULL | 0 |  |  |  |  |  |  |  |  | ✓ |  |  |  |  |  |  |  |  |  |  |
| EXISTS | 0, + |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| CMPS_EQ | 0, 0 |  |  |  |  |  |  |  |  | ✓ |  |  |  |  |  |  |  |  |  |  |
| CMPS_NE | 0, 0 |  |  |  |  |  |  |  |  | ✓ |  |  |  |  |  |  |  |  |  |  |
| G_MIN | (leaf) |  |  |  | C19.1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| G_AVG | (leaf) |  |  |  | C19.2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| G_MAX | (leaf) |  |  |  | C19.3 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| G_SUM | (leaf) |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| G_CNT | (leaf) |  |  |  | C20.2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| G_CNTD | (leaf) |  |  |  | C20.1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| G_CNTS | (leaf) |  |  |  | C20.3 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| GSEL | 0, + |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| AGG_MIN | 0 |  |  |  | C21.1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| AGG_AVG | 0 |  |  |  | C21.2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| AGG_MAX | + |  |  |  | C21.3 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| AGG_SUM | 0 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| AGG_CNT | + |  |  |  | C22.2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| AGG_CNTD | + |  |  |  | C22.1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| AGG_CNTS | + |  |  |  | C22.3 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| PLUS | +, + |  | β: 0 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |

## Laws

| id | name | instances | first instance |
|---|---|---|---|
| L1 | commutativity | 10 | `["UNION", "x", "y"] = ["UNION", "y", "x"]` |
| L2 | associativity | 10 | `["UNION", ["UNION", "x", "y"], "z"] = ["UNION", "x", ["UNION", "y", "z"]]` |
| L3 | involution | 3 | `["NOT_CA", ["NOT_CA", "x"]] = "x"` |
| L4 | De Morgan | 6 | `["NOT_CA", ["AND_CA", "x", "y"]] = ["OR_CA", ["NOT_CA", "x"], ["NOT_CA", "y"]]` |
| L5 | negated comparison | 40 | `["NOT_CA", ["CMP_CA_A_<", "x", "k"]] = ["CMP_CA_A_>=", "x", "k"]` |
| L6 | filter merge | 2 | `["DSEL", ["SEL", "t", "c"], "d"] = ["SEL", "t", ["AND_CA", "c", "d"]]` |
| L7 | filter swap | 2 | `["DSEL", ["SEL", "t", "c"], "d"] = ["DSEL", ["SEL", "t", "d"], "c"]` |
| L8 | difference of a union | 2 | `["EXCEPT", ["EXCEPT", "x", "y"], "z"] = ["EXCEPT", "x", ["UNION", "y", "z"]]` |
| L9 | difference swap | 2 | `["EXCEPT", ["EXCEPT", "x", "y"], "z"] = ["EXCEPT", ["EXCEPT", "x", "z"], "y"]` |
| L10 | filter through difference or intersection | 4 | `["DSEL", ["EXCEPT", "x", "y"], "c"] = ["EXCEPT", ["DSEL", "x", "c"], "y"]` |
| L11 | ON / WHERE exchange (INNER JOIN) | 2 | `["JSEL_INNER", "x", "y", "c", "d"] = ["JSEL_INNER", "x", "y", "d", "c"]` |
| L12 | ON merge (INNER JOIN) | 2 | `["JSEL_INNER", "x", "y", "c", "d"] = ["JSEL_INNER", "x", "y", ["AND_CAB", "c", "d"], ["TRUE_CAB"]]` |
| L13 | distinct union | 1 | `["DSELD", ["UNION_ALL", "x", "y"], ["TRUE_CA"]] = ["UNION", "x", "y"]` |
| L14 | derived-table merge | 2 | `["DSEL", ["TBL", "t"], "c"] = ["SEL", "t", "c"]` |
| L15 | WHERE TRUE | 1 | `["SEL", "t", ["TRUE_CA"]] = ["TBL", "t"]` |

## Sort extremes

- CA: greatest TRUE_CA, least FALSE_CA
- CAB: greatest TRUE_CAB, least FALSE_CAB
- H: greatest TRUE_H, least FALSE_H
