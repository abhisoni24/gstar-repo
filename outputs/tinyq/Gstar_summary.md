# G* for tinyq: summary

Inputs: inputs/tinyq/grammar.json, schema.json, table_T.json

G has 23 productions over 8 non-terminals; G* has 16 labelled non-terminals and 991 rules.

| kind | node kinds | rules from GTrans | rules after reduction |
|---|---|---|---|
| copy | 23 | 161 | 99 |
| swap | 16 | 124 | 56 |
| insert | 8 | 24 | 24 |
| drop | 8 | 24 | 24 |
| constant | 2 | 2 | 2 |
| law | 43 | 910 | 786 |
| total | 100 | 1245 | 991 |

Rules per labelled non-terminal (after reduction):

- Col.age[id]: 1
- Col.city[id]: 1
- Col.name[id]: 1
- Cond[=]: 87
- Cond[id]: 13
- Cond[↑]: 162
- Cond[↓]: 162
- Const.age[id]: 1
- Const.age[↑]: 1
- Const.age[↓]: 1
- Const.city[id]: 1
- Const.name[id]: 1
- Query[=]: 93
- Query[id]: 4
- Query[↑]: 231
- Query[↓]: 231

Labelled non-terminals removed by the reduction (they derive no pair, or are unreachable):

- Col.age[=]
- Col.age[↑]
- Col.age[↓]
- Col.city[=]
- Col.city[↑]
- Col.city[↓]
- Col.name[=]
- Col.name[↑]
- Col.name[↓]
- Const.age[=]
- Const.city[=]
- Const.city[↑]
- Const.city[↓]
- Const.name[=]
- Const.name[↑]
- Const.name[↓]

# Grammar G (built from grammar.json and schema.json)

- Col.age → col:age
- Col.city → col:city
- Col.name → col:name
- Cond → AND | OR | NOT | =[name] | <>[name] | <[age] | <=[age] | =[age] | >=[age] | >[age] | <>[age] | =[city] | <>[city]
- Const.age → const:age
- Const.city → const:city
- Const.name → const:name
- Query → People | WHERE | UNION | EXCEPT

