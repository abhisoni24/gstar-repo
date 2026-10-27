"""Inputs: the grammar G (built from a grammar template plus the database schema) and the table T."""
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, eq=False)
class Production:
    """One production of G. `op` is the operator name used to look up T (or BASE / COL / CONST for leaves)."""
    name: str            # unique id, e.g. "WHERE", ">[age]", "col:age", "const:age", "People"
    op: str              # key into T for operators; "BASE", "COL", "CONST" for leaves
    sort: str            # left-hand side non-terminal
    slots: tuple         # sorts of the argument slots, in order (alpha, beta) or (gamma)
    print_fmt: str       # how to print it, with {0}, {1} for the slots
    column: str = ""     # for atoms, columns and constants: the column
    domain: str = ""     # for constants: the name of the domain in Grammar.domains
    extra: dict = field(default_factory=dict, hash=False, compare=False)


@dataclass
class Grammar:
    start: str
    query_sort: str
    pred_sort: str
    productions: list
    domains: dict = field(default_factory=dict)   # column -> dict(type, values | min/max, ordered)

    def by_sort(self, sort):
        return [p for p in self.productions if p.sort == sort]

    def get(self, name):
        idx = self.__dict__.get("_index")
        if idx is None or len(idx) != len(self.productions):
            idx = {p.name: p for p in self.productions}
            self.__dict__["_index"] = idx
        return idx[name]

    @property
    def sorts(self):
        return sorted({p.sort for p in self.productions})


@dataclass
class Table:
    """T: per operator its slot signs, identity elements, bounds, order codes and laws; plus the law
    equations and, per sort, its greatest and least elements when G can write them."""
    ops: dict
    laws: list
    extremes: dict = field(default_factory=dict)

    def bound(self, op, slot):
        names = {0: ("alpha", "gamma"), 1: ("beta",)}
        b = self.ops.get(op, {}).get("bound", {})
        for n in names.get(slot, ()):
            if n in b:
                return b[n]
        return None

    def signs(self, op):
        return tuple(self.ops[op]["signs"])

    def identities(self, op):
        """Yield (slot index, value, extreme) with extreme in {"least", "greatest"}."""
        slot_index = {"alpha": 0, "beta": 1, "gamma": 0}
        for extreme, entries in self.ops.get(op, {}).get("identity", {}).items():
            for slot, value in entries.items():
                yield slot_index[slot], value, extreme

    def leq(self, f, g):
        """f ≼ g (pointwise), from the order codes Ci.j, closed under transitivity."""
        return (f, g) in self._order_closure()

    def _order_closure(self):
        if hasattr(self, "_closure"):
            return self._closure
        pairs = set()
        chains = {}
        for op, row in self.ops.items():
            for code in row.get("order", []):
                chain, rank = code[1:].split(".")
                chains.setdefault(chain, []).append((int(rank), op))
        for members in chains.values():
            for ra, a in members:
                for rb, b in members:
                    if ra < rb:
                        pairs.add((a, b))
        changed = True
        while changed:
            changed = False
            for (a, b) in list(pairs):
                for (c, d) in list(pairs):
                    if b == c and (a, d) not in pairs:
                        pairs.add((a, d))
                        changed = True
        self._closure = pairs
        return pairs


def load_grammar(grammar_path, schema_path):
    g = json.loads(Path(grammar_path).read_text())
    schema = json.loads(Path(schema_path).read_text())
    prods, domains = [], {}
    qs, ps = g["query_sort"], g["pred_sort"]
    # B: one production per base table of the schema
    for table in schema["tables"]:
        prods.append(Production(table, "BASE", qs, (), table))
    # W, op2, op1*, op2*: from the template
    for o in g["operators"]:
        prods.append(Production(o["op"], o["op"], o["sort"], tuple(o["slots"]), o["print"]))
    # A: for every column c, C_c θ K_c for each comparison θ allowed for c's type
    for table, tdef in schema["tables"].items():
        for col, cdef in tdef["columns"].items():
            ctype = cdef["type"]
            col_sort, const_sort = f"Col.{col}", f"Const.{col}"
            domains[col] = dict(cdef, ordered=(ctype in ("int", "float", "date")))
            prods.append(Production(f"col:{col}", "COL", col_sort, (), col, column=col))
            prods.append(Production(f"const:{col}", "CONST", const_sort, (), "k", column=col, domain=col))
            for theta in g["atoms"]["comparisons_by_type"][ctype]:
                fmt = g["atoms"]["print"].replace("{op}", theta)
                prods.append(Production(f"{theta}[{col}]", theta, ps, (col_sort, const_sort), fmt, column=col))
    return Grammar(g["start"], qs, ps, prods, domains)


def load_table(path):
    t = json.loads(Path(path).read_text())
    return Table(t["operators"], t["laws"], t.get("extremes", {}))


def load_grammar_explicit(path):
    """A grammar written out production by production (used for MySQL)."""
    g = json.loads(Path(path).read_text())
    prods = []
    for p in g["productions"]:
        prods.append(Production(p["name"], p["op"], p["sort"], tuple(p.get("slots", [])), p["print"],
                                column=p.get("column", ""), domain=p.get("domain", ""),
                                extra={k: v for k, v in p.items() if k not in
                                       ("name", "op", "sort", "slots", "print", "column", "domain")}))
    return Grammar(g["start"], g.get("query_sort", "Q"), g.get("pred_sort", "CA"), prods, g["domains"])
