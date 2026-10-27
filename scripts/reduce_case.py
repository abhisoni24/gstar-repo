"""Greedy reducer for a wrong-result case: shrink the query tree and the database while the engine's
result still differs from the reference evaluator's result.

Usage (as a module): reduce(g, tree, db, engine) -> (tree, db)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gtrans.refeval import Ref                      # noqa: E402
from gtrans.sqlexec import Printer, same_result     # noqa: E402


def as_tuple(t):
    return (t[0], tuple(as_tuple(k) for k in t[1]), t[2])


def nodes(t, path=()):
    yield path, t
    for i, k in enumerate(t[1]):
        yield from nodes(k, path + (i,))


def replace(t, path, new):
    if not path:
        return new
    i = path[0]
    kids = list(t[1])
    kids[i] = replace(kids[i], path[1:], new)
    return (t[0], tuple(kids), t[2])


def size(t):
    return 1 + sum(size(k) for k in t[1])


class Case:
    def __init__(self, g, engine, family_of):
        self.g, self.eng, self.pr, self.ref = g, engine, Printer(g), Ref()
        self.family_of = family_of
        self.n = 0

    def bad(self, tree, db):
        """True when the engine and the reference disagree on this statement."""
        self.n += 1
        try:
            self.ref.use("x", db)
            want = self.ref.run_tree(tree)
            self.eng.use(f"red{self.n % 2}", db)
            got = self.eng.run(self.pr.sql(tree))
        except Exception:                           # noqa: BLE001
            return False
        return not same_result(self.family_of(tree), got, want)

    def candidates(self, tree):
        sort = lambda t: self.g.get(t[0]).sort
        for path, n in sorted(nodes(tree), key=lambda pn: len(pn[0])):
            S = sort(n)
            subs = [m for p2, m in nodes(n) if p2 and sort(m) == S]
            if S == "Q":
                subs += [("TBL", (( f"TBL_{t}", (), None),), None) for t in ("t0", "t1", "t2")]
            if S in ("CA", "CAB", "H"):
                subs = [(f"TRUE_{S}", (), None), (f"FALSE_{S}", (), None)] + subs
            if S == "Tbl":
                subs = [(f"TBL_{t}", (), None) for t in ("t0", "t1", "t2")]
            for m in subs:
                if m != n and size(m) <= size(n):
                    yield replace(tree, path, m)

    def reduce(self, tree, db):
        tree = as_tuple(tree)
        assert self.bad(tree, db), "not a failing case"
        changed = True
        while changed:
            changed = False
            for cand in self.candidates(tree):
                if size(cand) < size(tree) or (size(cand) == size(tree) and self.pr.sql(cand) < self.pr.sql(tree)):
                    if self.bad(cand, db):
                        tree, changed = cand, True
                        break
            if changed:
                continue
            for t in db:                            # drop rows
                for i in range(len(db[t])):
                    db2 = {k: (v[:i] + v[i + 1:] if k == t else v) for k, v in db.items()}
                    if self.bad(tree, db2):
                        db, changed = db2, True
                        break
                if changed:
                    break
        return tree, db
