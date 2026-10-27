"""TinyQ semantics: building query trees, a reference evaluator, printers for TinyQ text and SQL, and SQLite."""
import random
import sqlite3

COMPARISONS = ("<", "<=", "=", ">=", ">", "<>")
PRETTY = {"<=": "≤", ">=": "≥", "<>": "≠"}


def build(prod, kids, const_value=None):
    """Turn a production plus already built children into a query tree (nested tuples)."""
    if prod.op == "BASE":
        return ("BASE", prod.name)
    if prod.op == "COL":
        return ("COL", prod.column)
    if prod.op == "CONST":
        return ("CONST", const_value)
    if prod.op in COMPARISONS:
        return ("CMP", prod.op, kids[0], kids[1])
    return (prod.op,) + tuple(kids)


# ---------------------------------------------------------------- reference evaluator (sets, 2-valued logic)
def _cmp(theta, v, k):
    return {"<": v < k, "<=": v <= k, "=": v == k, ">=": v >= k, ">": v > k, "<>": v != k}[theta]


def eval_cond(c, row, cols):
    tag = c[0]
    if tag == "CMP":
        return _cmp(c[1], row[cols[c[2][1]]], c[3][1])
    if tag == "AND":
        return eval_cond(c[1], row, cols) and eval_cond(c[2], row, cols)
    if tag == "OR":
        return eval_cond(c[1], row, cols) or eval_cond(c[2], row, cols)
    if tag == "NOT":
        return not eval_cond(c[1], row, cols)
    raise ValueError(tag)


def eval_query(q, db, cols):
    tag = q[0]
    if tag == "BASE":
        return frozenset(db[q[1]])
    if tag == "WHERE":
        return frozenset(r for r in eval_query(q[1], db, cols) if eval_cond(q[2], r, cols))
    if tag == "UNION":
        return eval_query(q[1], db, cols) | eval_query(q[2], db, cols)
    if tag == "EXCEPT":
        return eval_query(q[1], db, cols) - eval_query(q[2], db, cols)
    raise ValueError(tag)


# ---------------------------------------------------------------- printers
def _lit(v):
    return f"'{v}'" if isinstance(v, str) else str(v)


def show_cond(c):
    tag = c[0]
    if tag == "CMP":
        return f"{c[2][1]} {PRETTY.get(c[1], c[1])} {_lit(c[3][1])}"
    if tag == "NOT":
        return f"NOT ({show_cond(c[1])})"
    w = lambda x: f"({show_cond(x)})" if x[0] in ("AND", "OR") else show_cond(x)
    return f"{w(c[1])} {tag} {w(c[2])}"


def show_query(q):
    tag = q[0]
    if tag == "BASE":
        return q[1]
    w = lambda x: x[1] if x[0] == "BASE" else f"({show_query(x)})"
    if tag == "WHERE":
        return f"{w(q[1])} WHERE {show_cond(q[2])}"
    return f"{w(q[1])} {tag} {w(q[2])}"


def sql_cond(c):
    tag = c[0]
    if tag == "CMP":
        return f"{c[2][1]} {c[1]} {_lit(c[3][1])}"
    if tag == "NOT":
        return f"(NOT {sql_cond(c[1])})"
    return f"({sql_cond(c[1])} {tag} {sql_cond(c[2])})"


def sql_query(q):
    tag = q[0]
    if tag == "BASE":
        return f"SELECT * FROM {q[1]}"
    src = lambda x: x[1] if x[0] == "BASE" else f"({sql_query(x)})"
    if tag == "WHERE":
        return f"SELECT * FROM {src(q[1])} WHERE {sql_cond(q[2])}"
    return f"SELECT * FROM {src(q[1])} {tag} SELECT * FROM {src(q[2])}"


# ---------------------------------------------------------------- databases
def random_db(schema, rng, max_rows=7):
    """One random instance per table: distinct rows, no NULLs (the note's two-valued setting)."""
    db = {}
    for table, tdef in schema["tables"].items():
        cols = list(tdef["columns"])
        rows, n = set(), rng.randint(0, max_rows)
        while len(rows) < n:
            row = []
            for c in cols:
                cd = tdef["columns"][c]
                row.append(rng.choice(cd["values"]) if "values" in cd else rng.randint(cd["min"], cd["max"]))
            rows.add(tuple(row))
        db[table] = sorted(rows)
    return db


def column_index(schema):
    out = {}
    for tdef in schema["tables"].values():
        for i, c in enumerate(tdef["columns"]):
            out[c] = i
    return out


def sqlite_connect(schema, db):
    con = sqlite3.connect(":memory:")
    for table, tdef in schema["tables"].items():
        coldefs = ", ".join(f"{c} {'INTEGER' if d['type'] == 'int' else 'TEXT'} NOT NULL"
                            for c, d in tdef["columns"].items())
        con.execute(f"CREATE TABLE {table} ({coldefs})")
        marks = ", ".join("?" for _ in tdef["columns"])
        con.executemany(f"INSERT INTO {table} VALUES ({marks})", db[table])
    return con


def sqlite_eval(con, q):
    return frozenset(con.execute(sql_query(q)).fetchall())
