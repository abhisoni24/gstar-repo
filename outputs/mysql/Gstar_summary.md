# G* for mysql: summary

Inputs: inputs/mysql/grammar.json, table_T.json

G has 110 productions over 16 non-terminals; G* has 41 labelled non-terminals and 4294 rules.

| kind | node kinds | rules from GTrans | rules after reduction |
|---|---|---|---|
| copy | 110 | 1157 | 688 |
| swap | 138 | 1178 | 674 |
| insert | 23 | 69 | 69 |
| drop | 23 | 69 | 69 |
| extreme | 12 | 12 | 12 |
| constant | 4 | 4 | 4 |
| law | 162 | 3580 | 2778 |
| total | 472 | 6069 | 4294 |

Rules per labelled non-terminal (after reduction):

- CA[=]: 96
- CA[id]: 23
- CA[↑]: 175
- CA[↓]: 175
- CAB[=]: 107
- CAB[id]: 28
- CAB[↑]: 196
- CAB[↓]: 196
- ColAi[id]: 2
- ColAs[id]: 1
- ColBi[id]: 2
- ColBs[id]: 1
- GAgg[id]: 7
- GAgg[↑]: 6
- GAgg[↓]: 6
- GQ[=]: 3
- GQ[↑]: 2
- GQ[↓]: 2
- H[=]: 79
- H[id]: 11
- H[↑]: 197
- H[↓]: 197
- KInt[id]: 1
- KInt[↑]: 1
- KInt[↓]: 1
- KPos[id]: 1
- KPos[↑]: 1
- KPos[↓]: 1
- KStr[id]: 1
- Q[=]: 386
- Q[id]: 17
- Q[↑]: 1097
- Q[↓]: 1193
- Stmt[=]: 3
- Stmt[↑]: 3
- Stmt[↓]: 3
- Tbl[id]: 3
- V[=]: 8
- V[id]: 8
- V[↑]: 28
- V[↓]: 26

Labelled non-terminals removed by the reduction (they derive no pair, or are unreachable):

- ColAi[=]
- ColAi[↑]
- ColAi[↓]
- ColAs[=]
- ColAs[↑]
- ColAs[↓]
- ColBi[=]
- ColBi[↑]
- ColBi[↓]
- ColBs[=]
- ColBs[↑]
- ColBs[↓]
- GAgg[=]
- GQ[id]
- KInt[=]
- KPos[=]
- KStr[=]
- KStr[↑]
- KStr[↓]
- Stmt[id]
- Tbl[=]
- Tbl[↑]
- Tbl[↓]

# Grammar G (built from grammar.json and schema.json)

- CA → TRUE_CA | FALSE_CA | AND_CA | OR_CA | NOT_CA | CMP_CA_A_< | CMP_CA_A_<= | CMP_CA_A_= | CMP_CA_A_>= | CMP_CA_A_> | CMP_CA_A_<> | CMP_CA_AA_< | CMP_CA_AA_<= | CMP_CA_AA_= | CMP_CA_AA_>= | CMP_CA_AA_> | CMP_CA_AA_<> | CMPS_CA_EQ | CMPS_CA_NE | BETW_CA | ISNULL_CA | ISNOTNULL_CA | EXISTS_CA
- CAB → TRUE_CAB | FALSE_CAB | AND_CAB | OR_CAB | NOT_CAB | CMP_CAB_A_< | CMP_CAB_A_<= | CMP_CAB_A_= | CMP_CAB_A_>= | CMP_CAB_A_> | CMP_CAB_A_<> | CMP_CAB_B_< | CMP_CAB_B_<= | CMP_CAB_B_= | CMP_CAB_B_>= | CMP_CAB_B_> | CMP_CAB_B_<> | CMP_CAB_AB_< | CMP_CAB_AB_<= | CMP_CAB_AB_= | CMP_CAB_AB_>= | CMP_CAB_AB_> | CMP_CAB_AB_<> | CMPS_CAB_EQ | CMPS_CAB_NE | BETW_CAB | ISNULL_CAB | ISNOTNULL_CAB
- ColAi → COL_ac0 | COL_ac1
- ColAs → COL_ac2
- ColBi → COL_bc0 | COL_bc1
- ColBs → COL_bc2
- GAgg → G_MIN | G_AVG | G_MAX | G_SUM | G_CNT | G_CNTD | G_CNTS
- GQ → GSEL
- H → TRUE_H | FALSE_H | AND_H | OR_H | NOT_H | CMP_H_G_< | CMP_H_G_<= | CMP_H_G_= | CMP_H_G_>= | CMP_H_G_> | CMP_H_G_<>
- KInt → K_INT
- KPos → K_POS
- KStr → K_STR
- Q → TBL | SEL | SELD | DSEL | DSELD | JSEL_INNER | JDSEL_INNER | JSEL_LEFT | JDSEL_LEFT | JSEL_RIGHT | JDSEL_RIGHT | UNION | UNION_ALL | INTERSECT | INTERSECT_ALL | EXCEPT | EXCEPT_ALL
- Stmt → STMT_Q | STMT_V | STMT_G
- Tbl → TBL_t0 | TBL_t1 | TBL_t2
- V → AGG_MIN | AGG_AVG | AGG_MAX | AGG_SUM | AGG_CNT | AGG_CNTD | AGG_CNTS | PLUS

