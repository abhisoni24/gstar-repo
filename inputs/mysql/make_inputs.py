"""Write grammar.json and table_T.json for MySQL.

G is the core of ValScope's grammar (documents/pinolo_extension_bnf.md in the ValScope repository) that fits
the assumptions of the note: no context (no CTE), deterministic operators (no LIMIT), and constructs whose
facts we can state for MySQL's bags and three-valued logic. Left out: CTE (WITH), FOR UPDATE, ORDER BY,
LIMIT, CASE, arbitrary function calls, LIKE, REGEXP, IN. See README_mysql.md for the mapping.

Schema of every table t0, t1, t2: (c0 INT, c1 INT, c2 VARCHAR(8)), all nullable, duplicates allowed.
Every row query returns the three columns c0, c1, c2 (so set operations are always union-compatible).

This script only writes the two JSON files; they are the inputs that GTrans reads.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CMP = ["<", "<=", "=", ">=", ">", "<>"]
COMP = {"<": ">=", ">=": "<", "<=": ">", ">": "<=", "=": "<>", "<>": "="}
# signs of 'x θ y' in (x, y), in the truth order FALSE < UNKNOWN < TRUE
CMP_SIGNS = {"<": ["-", "+"], "<=": ["-", "+"], ">": ["+", "-"], ">=": ["+", "-"], "=": ["0", "0"], "<>": ["0", "0"]}
CMP_CHAINS = [("<", "<="), ("=", "<="), ("=", ">="), (">", ">="), ("<", "<>"), (">", "<>")]
SEL = "SELECT a.c0, a.c1, a.c2"

P = []          # productions
OPS = {}        # rows of T


def prod(name, op, sort, slots, pr, **kw):
    P.append(dict(name=name, op=op, sort=sort, slots=slots, print=pr, **kw))


def row(op, signs, **kw):
    OPS.setdefault(op, dict(signs=signs, identity={}, bound={}, order=[], laws=[]))
    OPS[op].update(kw)


chain_no = [0]


def chain(*ops):
    chain_no[0] += 1
    for rank, op in enumerate(ops, 1):
        OPS[op]["order"].append(f"C{chain_no[0]}.{rank}")


# ------------------------------------------------------------------ start symbol and the three kinds of statement
prod("STMT_Q", "WRAP", "Stmt", ["Q"], "{0}", family="rows")
prod("STMT_V", "WRAP", "Stmt", ["V"], "{0}", family="value")
prod("STMT_G", "WRAP", "Stmt", ["GQ"], "{0}", family="groups")
row("WRAP", ["+"])

# ------------------------------------------------------------------ leaves from the schema
for t in ("t0", "t1", "t2"):
    prod(f"TBL_{t}", "LEAF", "Tbl", [], t)
for al in ("a", "b"):
    for c in ("c0", "c1"):
        prod(f"COL_{al}{c}", "LEAF", f"Col{al.upper()}i", [], f"{al}.{c}")
    prod(f"COL_{al}c2", "LEAF", f"Col{al.upper()}s", [], f"{al}.c2")
prod("K_INT", "CONST", "KInt", [], "{k}", domain="int")
prod("K_STR", "CONST", "KStr", [], "{k}", domain="str")
prod("K_POS", "CONST", "KPos", [], "{k}", domain="pos")

# ------------------------------------------------------------------ row queries Q (bags of (c0, c1, c2))
prod("TBL", "TBL", "Q", ["Tbl"], f"{SEL} FROM {{0}} AS a")
prod("SEL", "SEL", "Q", ["Tbl", "CA"], f"{SEL} FROM {{0}} AS a WHERE {{1}}")
prod("SELD", "SELD", "Q", ["Tbl", "CA"], f"SELECT DISTINCT a.c0, a.c1, a.c2 FROM {{0}} AS a WHERE {{1}}")
prod("DSEL", "DSEL", "Q", ["Q", "CA"], f"{SEL} FROM ({{0}}) AS a WHERE {{1}}")
prod("DSELD", "DSELD", "Q", ["Q", "CA"], f"SELECT DISTINCT a.c0, a.c1, a.c2 FROM ({{0}}) AS a WHERE {{1}}")
row("TBL", ["0"])
row("SEL", ["0", "+"])
row("SELD", ["0", "+"])
row("DSEL", ["+", "+"], identity={"greatest": {"beta": "TRUE"}}, bound={"alpha": "deflationary"})
row("DSELD", ["+", "+"], bound={"alpha": "deflationary"})
chain("SELD", "SEL")
chain("DSELD", "DSEL")
for k in ("INNER", "LEFT", "RIGHT"):
    prod(f"JSEL_{k}", f"JSEL_{k}", "Q", ["Tbl", "Tbl", "CAB", "CAB"],
         f"{SEL} FROM {{0}} AS a {k} JOIN {{1}} AS b ON {{2}} WHERE {{3}}")
    prod(f"JDSEL_{k}", f"JDSEL_{k}", "Q", ["Q", "Q", "CAB", "CAB"],
         f"{SEL} FROM ({{0}}) AS a {k} JOIN ({{1}}) AS b ON {{2}} WHERE {{3}}")
# ON is monotone only for INNER; for outer joins a new match removes a NULL-extended row (sign 0).
row("JSEL_INNER", ["0", "0", "+", "+"])
row("JSEL_LEFT", ["0", "0", "0", "+"])
row("JSEL_RIGHT", ["0", "0", "0", "+"])
row("JDSEL_INNER", ["+", "+", "+", "+"])
row("JDSEL_LEFT", ["+", "0", "0", "+"])
row("JDSEL_RIGHT", ["0", "+", "0", "+"])
chain("JSEL_INNER", "JSEL_LEFT")
chain("JSEL_INNER", "JSEL_RIGHT")
chain("JDSEL_INNER", "JDSEL_LEFT")
chain("JDSEL_INNER", "JDSEL_RIGHT")
SETOPS = {"UNION": "UNION", "UNION_ALL": "UNION ALL", "INTERSECT": "INTERSECT",
          "INTERSECT_ALL": "INTERSECT ALL", "EXCEPT": "EXCEPT", "EXCEPT_ALL": "EXCEPT ALL"}
for name, kw in SETOPS.items():
    prod(name, name, "Q", ["Q", "Q"], f"({{0}}) {kw} ({{1}})")
row("UNION", ["+", "+"])
row("UNION_ALL", ["+", "+"], identity={"least": {"alpha": "EMPTY", "beta": "EMPTY"}})
row("INTERSECT", ["+", "+"], bound={"alpha": "deflationary", "beta": "deflationary"})
row("INTERSECT_ALL", ["+", "+"], bound={"alpha": "deflationary", "beta": "deflationary"})
row("EXCEPT", ["+", "-"], bound={"alpha": "deflationary"})
row("EXCEPT_ALL", ["+", "-"], identity={"least": {"beta": "EMPTY"}})
chain("INTERSECT", "INTERSECT_ALL", "UNION_ALL")
chain("INTERSECT", "UNION", "UNION_ALL")
chain("EXCEPT", "EXCEPT_ALL", "UNION_ALL")
chain("EXCEPT", "UNION")

# ------------------------------------------------------------------ predicates: CA (alias a), CAB (a and b), H (HAVING)
row("TRUE", [])
row("FALSE", [])
row("AND", ["+", "+"], identity={"greatest": {"alpha": "TRUE", "beta": "TRUE"}})
row("OR", ["+", "+"], identity={"least": {"alpha": "FALSE", "beta": "FALSE"}})
row("NOT", ["-"])
chain("FALSE", "TRUE")
chain("AND", "OR")
for th in CMP:
    row(th, CMP_SIGNS[th])
for lo, hi in CMP_CHAINS:
    chain(lo, hi)
row("BETWEEN", ["0", "-", "+"])
row("ISNULL", ["0"])
row("ISNOTNULL", ["0"])
row("EXISTS", ["0", "+"])
row("CMPS_EQ", ["0", "0"])
row("CMPS_NE", ["0", "0"])

EXTREMES = {}
for S in ("CA", "CAB", "H"):
    prod(f"TRUE_{S}", "TRUE", S, [], "TRUE")
    prod(f"FALSE_{S}", "FALSE", S, [], "FALSE")
    prod(f"AND_{S}", "AND", S, [S, S], "({0}) AND ({1})")
    prod(f"OR_{S}", "OR", S, [S, S], "({0}) OR ({1})")
    prod(f"NOT_{S}", "NOT", S, [S], "NOT ({0})")
    EXTREMES[S] = {"greatest": f"TRUE_{S}", "least": f"FALSE_{S}"}

ATOM_FAMILIES = [  # (sort, tag, slots) for 'x θ y' atoms
    ("CA", "A", ["ColAi", "KInt"]), ("CA", "AA", ["ColAi", "ColAi"]),
    ("CAB", "A", ["ColAi", "KInt"]), ("CAB", "B", ["ColBi", "KInt"]), ("CAB", "AB", ["ColAi", "ColBi"]),
    ("H", "G", ["GAgg", "KInt"]),
]
for S, tag, slots in ATOM_FAMILIES:
    for th in CMP:
        prod(f"CMP_{S}_{tag}_{th}", th, S, slots, f"{{0}} {th} {{1}}")
for S, col in (("CA", "ColAs"), ("CAB", "ColBs")):
    prod(f"CMPS_{S}_EQ", "CMPS_EQ", S, [col, "KStr"], "{0} = {1}")
    prod(f"CMPS_{S}_NE", "CMPS_NE", S, [col, "KStr"], "{0} <> {1}")
for S, col in (("CA", "ColAi"), ("CAB", "ColBi")):
    prod(f"BETW_{S}", "BETWEEN", S, [col, "KInt", "KInt"], "{0} BETWEEN {1} AND {2}")
    prod(f"ISNULL_{S}", "ISNULL", S, [col], "{0} IS NULL")
    prod(f"ISNOTNULL_{S}", "ISNOTNULL", S, [col], "{0} IS NOT NULL")
prod("EXISTS_CA", "EXISTS", "CA", ["Tbl", "CAB"], "EXISTS (SELECT 1 FROM {0} AS b WHERE {1})")

# ------------------------------------------------------------------ aggregates
# Inside HAVING every group is non-empty, so MIN ≤ AVG ≤ MAX and the three are NULL together.
for name, pr in (("MIN", "MIN(a.c0)"), ("AVG", "AVG(a.c0)"), ("MAX", "MAX(a.c0)"), ("SUM", "SUM(a.c0)"),
                 ("CNT", "COUNT(a.c0)"), ("CNTD", "COUNT(DISTINCT a.c0)"), ("CNTS", "COUNT(*)")):
    prod(f"G_{name}", f"G_{name}", "GAgg", [], pr)
    row(f"G_{name}", [])
chain("G_MIN", "G_AVG", "G_MAX")
chain("G_CNTD", "G_CNT", "G_CNTS")
prod("GSEL", "GSEL", "GQ", ["Q", "H"], "SELECT a.c1, COUNT(*) FROM ({0}) AS a GROUP BY a.c1 HAVING {1}")
row("GSEL", ["0", "+"])     # the input bag changes group values: no direction; HAVING filters groups: +

# Scalar aggregate over a query. Value order: NULL is the least value (an aggregate of an empty input).
# In that order MAX and the COUNTs grow with their input; MIN, AVG and SUM have no guaranteed direction.
for name, pr, sg in (("MIN", "MIN(a.c0)", "0"), ("AVG", "AVG(a.c0)", "0"), ("MAX", "MAX(a.c0)", "+"),
                     ("SUM", "SUM(a.c0)", "0"), ("CNT", "COUNT(a.c0)", "+"), ("CNTD", "COUNT(DISTINCT a.c0)", "+"),
                     ("CNTS", "COUNT(*)", "+")):
    prod(f"AGG_{name}", f"AGG_{name}", "V", ["Q"], pr, agg=True)
    row(f"AGG_{name}", [sg])
chain("AGG_MIN", "AGG_AVG", "AGG_MAX")
chain("AGG_CNTD", "AGG_CNT", "AGG_CNTS")
prod("PLUS", "PLUS", "V", ["V", "KPos"], "{0} + {1}")
row("PLUS", ["+", "+"], identity={"least": {"beta": "0"}})

# ------------------------------------------------------------------ laws (linear; valid under bags and 3VL)
LAWS = []


def law(lid, name, instances):
    LAWS.append({"id": lid, "name": name, "instances_from": instances})
    ops = set()

    def walk(x):
        if isinstance(x, list):
            pp = next(p for p in P if p["name"] == x[0])
            ops.add(pp["op"])
            for k in x[1:]:
                walk(k)
    for inst in instances:
        walk(inst["lhs"]), walk(inst["rhs"])
    for op in ops:
        if op in OPS and lid not in OPS[op]["laws"]:
            OPS[op]["laws"].append(lid)


I = lambda l, r: {"lhs": l, "rhs": r}
comm_ops = ["UNION", "UNION_ALL", "INTERSECT", "INTERSECT_ALL"] + [f"{o}_{S}" for S in ("CA", "CAB", "H") for o in ("AND", "OR")]
law("L1", "commutativity", [I([f, "x", "y"], [f, "y", "x"]) for f in comm_ops])
law("L2", "associativity", [I([f, [f, "x", "y"], "z"], [f, "x", [f, "y", "z"]]) for f in comm_ops])
law("L3", "involution", [I([f"NOT_{S}", [f"NOT_{S}", "x"]], "x") for S in ("CA", "CAB", "H")])
law("L4", "De Morgan", [I([f"NOT_{S}", [f"{a}_{S}", "x", "y"]], [f"{b}_{S}", [f"NOT_{S}", "x"], [f"NOT_{S}", "y"]])
                        for S in ("CA", "CAB", "H") for a, b in (("AND", "OR"), ("OR", "AND"))])
neg = []
for S, tag, slots in ATOM_FAMILIES:
    for th in CMP:
        neg.append(I([f"NOT_{S}", [f"CMP_{S}_{tag}_{th}", "x", "k"]], [f"CMP_{S}_{tag}_{COMP[th]}", "x", "k"]))
for S in ("CA", "CAB"):
    neg.append(I([f"NOT_{S}", [f"CMPS_{S}_EQ", "x", "k"]], [f"CMPS_{S}_NE", "x", "k"]))
    neg.append(I([f"NOT_{S}", [f"ISNULL_{S}", "x"]], [f"ISNOTNULL_{S}", "x"]))
law("L5", "negated comparison", neg)
law("L6", "filter merge", [I(["DSEL", ["SEL", "t", "c"], "d"], ["SEL", "t", ["AND_CA", "c", "d"]]),
                           I(["DSEL", ["DSEL", "x", "c"], "d"], ["DSEL", "x", ["AND_CA", "c", "d"]])])
law("L7", "filter swap", [I(["DSEL", ["SEL", "t", "c"], "d"], ["DSEL", ["SEL", "t", "d"], "c"]),
                          I(["DSEL", ["DSEL", "x", "c"], "d"], ["DSEL", ["DSEL", "x", "d"], "c"])])
law("L8", "difference of a union", [I(["EXCEPT", ["EXCEPT", "x", "y"], "z"], ["EXCEPT", "x", ["UNION", "y", "z"]]),
                                    I(["EXCEPT_ALL", ["EXCEPT_ALL", "x", "y"], "z"], ["EXCEPT_ALL", "x", ["UNION_ALL", "y", "z"]])])
law("L9", "difference swap", [I([e, [e, "x", "y"], "z"], [e, [e, "x", "z"], "y"]) for e in ("EXCEPT", "EXCEPT_ALL")])
law("L10", "filter through difference or intersection",
    [I(["DSEL", [o, "x", "y"], "c"], [o, ["DSEL", "x", "c"], "y"]) for o in ("EXCEPT", "EXCEPT_ALL", "INTERSECT", "INTERSECT_ALL")])
law("L11", "ON / WHERE exchange (INNER JOIN)", [I([j, "x", "y", "c", "d"], [j, "x", "y", "d", "c"]) for j in ("JSEL_INNER", "JDSEL_INNER")])
law("L12", "ON merge (INNER JOIN)", [I([j, "x", "y", "c", "d"], [j, "x", "y", ["AND_CAB", "c", "d"], ["TRUE_CAB"]]) for j in ("JSEL_INNER", "JDSEL_INNER")])
law("L13", "distinct union", [I(["DSELD", ["UNION_ALL", "x", "y"], ["TRUE_CA"]], ["UNION", "x", "y"])])
law("L14", "derived-table merge", [I(["DSEL", ["TBL", "t"], "c"], ["SEL", "t", "c"]), I(["DSELD", ["TBL", "t"], "c"], ["SELD", "t", "c"])])
law("L15", "WHERE TRUE", [I(["SEL", "t", ["TRUE_CA"]], ["TBL", "t"])])

grammar = {
    "_comment": "G for MySQL: the core of ValScope's grammar. Written by make_inputs.py.",
    "start": "Stmt", "query_sort": "Q", "pred_sort": "CA",
    "domains": {"int": {"type": "int", "min": -3, "max": 12, "ordered": True},
                "pos": {"type": "int", "min": 0, "max": 9, "ordered": True},
                "str": {"type": "text", "values": ["a", "b", "c", "ab", "ba"], "ordered": False}},
    "productions": P,
}
table = {
    "_comment": "T for MySQL 9.x: bags, three-valued logic (FALSE < UNKNOWN < TRUE), NULLs in data. "
                "signs: one per slot; identity: greatest / least per slot; bound: f(x, ·) ⊑ x (deflationary) or "
                "x ⊑ f(x, ·) (inflationary) for x in that slot; order: codes Ci.j; laws: ids. Written by make_inputs.py.",
    "operators": OPS, "laws": LAWS, "extremes": EXTREMES,
}
(HERE / "grammar.json").write_text(json.dumps(grammar, indent=1, ensure_ascii=False))
(HERE / "table_T.json").write_text(json.dumps(table, indent=1, ensure_ascii=False))
print(f"{len(P)} productions, {len(OPS)} operator rows, {len(LAWS)} laws "
      f"({sum(len(l['instances_from']) for l in LAWS)} instances)")
