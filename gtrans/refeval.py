"""Reference evaluator for MySQL G trees: bags, NULLs, three-valued logic.

It is written from the SQL standard / MySQL manual semantics of each construct in G, independently of any
engine, and is used (1) to decide which engine is right when two engines disagree and (2) to check T itself:
if the reference violates metRel(Q, Q′) for a pair, T (or the reference) is wrong, not the engine.

A tree is (production name, children, constant), as built by sqlexec.builder.
Truth values: True, False, None (UNKNOWN). Rows: tuples (c0, c1, c2). A bag: a list of rows.
"""
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction

CMP = {
    "<": lambda x, y: x < y, "<=": lambda x, y: x <= y, "=": lambda x, y: x == y,
    ">=": lambda x, y: x >= y, ">": lambda x, y: x > y, "<>": lambda x, y: x != y,
}
COL = {"c0": 0, "c1": 1, "c2": 2}
NULL_ROW = (None, None, None)


def k_and(x, y):
    if x is False or y is False:
        return False
    if x is None or y is None:
        return None
    return True


def k_or(x, y):
    if x is True or y is True:
        return True
    if x is None or y is None:
        return None
    return False


def k_not(x):
    return None if x is None else (not x)


def k_cmp(th, x, y):
    if x is None or y is None:
        return None
    return CMP[th](x, y)


def distinct(rows):
    seen, out = set(), []
    for r in rows:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


class Ref:
    name = "reference"
    version = "bag/3VL reference (gtrans.refeval)"

    def __init__(self):
        self.db = None

    def use(self, dbname, db):
        self.db = {t: [tuple(r) for r in rows] for t, rows in db.items()}

    # ------------------------------------------------------------ statements
    def run_tree(self, t):
        name, kids, _ = t
        if name == "STMT_Q":
            return self.q(kids[0])
        if name == "STMT_V":
            return [(self.v(kids[0]),)]
        if name == "STMT_G":
            return self.gq(kids[0])
        raise ValueError(name)

    # ------------------------------------------------------------ leaves
    @staticmethod
    def const(t):
        return t[2]

    def table(self, t):
        return list(self.db[t[0][len("TBL_"):]])

    @staticmethod
    def col(t, env):
        name = t[0]                       # COL_ac0, COL_bc2, ...
        alias, c = name[4], name[5:]
        row = env[alias]
        return row[COL[c]]

    # ------------------------------------------------------------ row queries
    def q(self, t):
        name, kids, _ = t
        if name == "TBL":
            return self.table(kids[0])
        if name in ("SEL", "SELD"):
            rows = [r for r in self.table(kids[0]) if self.pred(kids[1], {"a": r}) is True]
            return distinct(rows) if name == "SELD" else rows
        if name in ("DSEL", "DSELD"):
            rows = [r for r in self.q(kids[0]) if self.pred(kids[1], {"a": r}) is True]
            return distinct(rows) if name == "DSELD" else rows
        if name.startswith("JSEL_") or name.startswith("JDSEL_"):
            kind = name.split("_")[1]
            if name.startswith("JSEL_"):
                A, B = self.table(kids[0]), self.table(kids[1])
            else:
                A, B = self.q(kids[0]), self.q(kids[1])
            on, where = kids[2], kids[3]
            joined, b_matched = [], [False] * len(B)
            for ra in A:
                hit = False
                for j, rb in enumerate(B):
                    if self.pred(on, {"a": ra, "b": rb}) is True:
                        joined.append((ra, rb))
                        hit = True
                        b_matched[j] = True
                if not hit and kind == "LEFT":
                    joined.append((ra, NULL_ROW))
            if kind == "RIGHT":
                # RIGHT JOIN keeps every b row: matched pairs as above, unmatched b rows NULL-extended
                joined += [(NULL_ROW, rb) for j, rb in enumerate(B) if not b_matched[j]]
            return [ra for (ra, rb) in joined if self.pred(where, {"a": ra, "b": rb}) is True]
        if name in ("UNION", "UNION_ALL", "INTERSECT", "INTERSECT_ALL", "EXCEPT", "EXCEPT_ALL"):
            x, y = self.q(kids[0]), self.q(kids[1])
            if name == "UNION_ALL":
                return x + y
            if name == "UNION":
                return distinct(x + y)
            cx, cy = Counter(x), Counter(y)
            if name == "INTERSECT":
                return [r for r in distinct(x) if cy[r] > 0]
            if name == "INTERSECT_ALL":
                return [r for r in distinct(x) for _ in range(min(cx[r], cy[r]))]
            if name == "EXCEPT":
                return [r for r in distinct(x) if cy[r] == 0]
            if name == "EXCEPT_ALL":
                return [r for r in distinct(x) for _ in range(max(cx[r] - cy[r], 0))]
        raise ValueError(name)

    # ------------------------------------------------------------ predicates (CA, CAB, H)
    def pred(self, t, env, group=None):
        name, kids, _ = t
        op = name.split("_")[0]
        if op == "TRUE":
            return True
        if op == "FALSE":
            return False
        if op == "AND":
            return k_and(self.pred(kids[0], env, group), self.pred(kids[1], env, group))
        if op == "OR":
            return k_or(self.pred(kids[0], env, group), self.pred(kids[1], env, group))
        if op == "NOT":
            return k_not(self.pred(kids[0], env, group))
        if op == "CMP":
            th = name.rsplit("_", 1)[1]
            return k_cmp(th, self.term(kids[0], env, group), self.term(kids[1], env, group))
        if op == "CMPS":
            th = "=" if name.endswith("_EQ") else "<>"
            return k_cmp(th, self.term(kids[0], env, group), self.term(kids[1], env, group))
        if op == "BETW":
            x, lo, hi = (self.term(k, env, group) for k in kids)
            return k_and(k_cmp(">=", x, lo), k_cmp("<=", x, hi))
        if op == "ISNULL":
            return self.term(kids[0], env, group) is None
        if op == "ISNOTNULL":
            return self.term(kids[0], env, group) is not None
        if op == "EXISTS":
            return any(self.pred(kids[1], {"a": env["a"], "b": rb}) is True for rb in self.table(kids[0]))
        raise ValueError(name)

    def term(self, t, env, group):
        name = t[0]
        if name.startswith("COL_"):
            return self.col(t, env)
        if name.startswith("K_"):
            return self.const(t)
        if name.startswith("G_"):
            return self.agg(name[2:], [r[0] for r in group])
        raise ValueError(name)

    # ------------------------------------------------------------ aggregates over a column of values
    @staticmethod
    def agg(kind, vals):
        nn = [v for v in vals if v is not None]
        if kind == "CNTS":
            return len(vals)
        if kind == "CNT":
            return len(nn)
        if kind == "CNTD":
            return len(set(nn))
        if not nn:
            return None
        if kind == "MIN":
            return min(nn)
        if kind == "MAX":
            return max(nn)
        if kind == "SUM":
            return sum(nn)
        if kind == "AVG":
            return Fraction(sum(nn), len(nn))
        raise ValueError(kind)

    def v(self, t):
        name, kids, _ = t
        if name.startswith("AGG_"):
            return self._num(self.agg(name[4:], [r[0] for r in self.q(kids[0])]))
        if name == "PLUS":
            x = self.v(kids[0])
            return None if x is None else x + self.const(kids[1])
        raise ValueError(name)

    @staticmethod
    def _num(x):
        if isinstance(x, Fraction):          # MySQL: AVG of INT is DECIMAL with 4 more digits
            return (Decimal(x.numerator) / Decimal(x.denominator)).quantize(Decimal("0.0001"), ROUND_HALF_UP)
        return x

    def gq(self, t):
        name, kids, _ = t
        assert name == "GSEL"
        groups = {}
        for r in self.q(kids[0]):
            groups.setdefault(r[1], []).append(r)
        return [(k, len(rows)) for k, rows in groups.items() if self.pred(kids[1], {}, group=rows) is True]
