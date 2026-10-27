"""MySQL target: tree builder, SQL printer, random databases, execution on MySQL and DuckDB, and the oracle.

A tree is (production name, children, constant). The statement family is decided by the root production:
STMT_Q (bag of rows), STMT_V (one value) or STMT_G (bag of (group key, count) rows).
"""
import random
from collections import Counter
from decimal import Decimal

UP, DN, EQ = "↑", "↓", "="


def builder(prod, kids, const=None):
    return (prod.name, tuple(kids), const)


class Printer:
    def __init__(self, g):
        self.g = g

    def sql(self, node):
        name, kids, const = node
        p = self.g.get(name)
        if p.op == "CONST":
            return f"'{const}'" if p.domain == "str" else str(const)
        if name == "STMT_V":
            expr, src = self.value(kids[0])
            return f"SELECT {expr} FROM ({src}) AS a"
        return p.print_fmt.format(*[self.sql(k) for k in kids])

    def value(self, node):
        name, kids, const = node
        p = self.g.get(name)
        if p.extra.get("agg"):
            return p.print_fmt, self.sql(kids[0])
        if name == "PLUS":
            e, s = self.value(kids[0])
            return f"{e} + {self.sql(kids[1])}", s
        raise ValueError(name)

    @staticmethod
    def family(node):
        return {"STMT_Q": "rows", "STMT_V": "value", "STMT_G": "groups"}[node[0]]


# ---------------------------------------------------------------- databases: bags with NULLs
INTS = list(range(-3, 13))
STRS = ["a", "b", "c", "ab", "ba"]


def random_db(rng, max_rows=8, p_null=0.15):
    db = {}
    for t in ("t0", "t1", "t2"):
        rows = []
        for _ in range(rng.randint(0, max_rows)):
            if rows and rng.random() < 0.2:
                rows.append(rng.choice(rows))          # duplicates: tables are bags
                continue
            rows.append(tuple(None if rng.random() < p_null else v for v in
                              (rng.choice(INTS), rng.choice(INTS), rng.choice(STRS))))
        db[t] = rows
    return db


def _lit(v):
    return "NULL" if v is None else (f"'{v}'" if isinstance(v, str) else str(v))


def load_statements(db):
    out = []
    for t, rows in db.items():
        out.append(f"DROP TABLE IF EXISTS {t}")
        out.append(f"CREATE TABLE {t} (c0 INT, c1 INT, c2 VARCHAR(8))")
        if rows:
            out.append(f"INSERT INTO {t} VALUES " + ", ".join("(" + ", ".join(_lit(v) for v in r) + ")" for r in rows))
    return out


# ---------------------------------------------------------------- normalization and the oracle
def norm_value(v):
    if isinstance(v, (Decimal, float)):
        return Decimal(str(round(float(v), 4))) if isinstance(v, float) else v
    return v


def norm_rows(rows):
    return Counter(tuple(norm_value(v) for v in r) for r in rows)


def scalar(rows):
    assert len(rows) == 1 and len(rows[0]) == 1, rows
    return norm_value(rows[0][0])


def value_leq(a, b):
    """NULL is the least value (an aggregate of an empty input)."""
    if a is None:
        return True
    if b is None:
        return False
    return a <= b


def holds(family, label, ra, rb):
    """Does metRel(Q, Q′) given by `label` hold for results ra, rb (lists of tuples)?"""
    if family == "value":
        a, b = scalar(ra), scalar(rb)
        if label == EQ:
            return value_leq(a, b) and value_leq(b, a)
        return value_leq(a, b) if label == UP else value_leq(b, a)
    A, B = norm_rows(ra), norm_rows(rb)
    if label == EQ:
        return A == B
    small, big = (A, B) if label == UP else (B, A)
    return all(big[k] >= n for k, n in small.items())


def same_result(family, ra, rb, tol=Decimal("0.001")):
    """Compare one query's results from two engines (numbers within tol)."""
    def close(x, y):
        if isinstance(x, (Decimal, int, float)) and isinstance(y, (Decimal, int, float)) and not isinstance(x, bool):
            return abs(Decimal(str(x)) - Decimal(str(y))) <= tol
        return x == y
    if family == "value":
        a, b = scalar(ra), scalar(rb)
        return (a is None and b is None) or (a is not None and b is not None and close(a, b))
    A = sorted((tuple(norm_value(v) for v in r) for r in ra), key=repr)
    B = sorted((tuple(norm_value(v) for v in r) for r in rb), key=repr)
    if len(A) != len(B):
        return False
    ka, kb = Counter(map(_key, A)), Counter(map(_key, B))
    return ka == kb


def _key(row):
    return tuple(float(v) if isinstance(v, Decimal) else v for v in row)


# ---------------------------------------------------------------- engines
class MySQL:
    def __init__(self, port, name, password="gt"):
        import pymysql
        self.name = name
        self.con = pymysql.connect(host="127.0.0.1", port=port, user="root", password=password, autocommit=True)
        self.cur = self.con.cursor()
        self.cur.execute("SELECT VERSION()")
        self.version = self.cur.fetchone()[0]

    def use(self, dbname, db):
        self.cur.execute(f"CREATE DATABASE IF NOT EXISTS {dbname}")
        self.cur.execute(f"USE {dbname}")
        for s in load_statements(db):
            self.cur.execute(s)
        self.cur.execute("SET SESSION max_execution_time = 10000")

    def run(self, sql):
        self.cur.execute(sql)
        return list(self.cur.fetchall())


class DuckDB:
    def __init__(self):
        import duckdb
        self.name, self.mod = "duckdb", duckdb
        self.version = duckdb.__version__
        self.cons = {}

    def use(self, dbname, db):
        key = repr(sorted(db.items()))          # reload when the same name is reused with other data
        if dbname not in self.cons or self.cons[dbname][0] != key:
            if dbname in self.cons:
                self.cons[dbname][1].close()
            con = self.mod.connect()
            for s in load_statements(db):
                con.execute(s)
            self.cons[dbname] = (key, con)
        self.con = self.cons[dbname][1]

    def run(self, sql):
        return [tuple(r) for r in self.con.execute(sql).fetchall()]
