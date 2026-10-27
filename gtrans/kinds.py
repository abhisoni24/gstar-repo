"""Node kinds (Table 3 of the note): copy, swap, insert, drop, constant, law.

A node kind is one way a node of a pair tree can look. It has a Q-side pattern and a Q′-side pattern
over the same shared variables (the shared children), possibly a fresh subtree on one side, and its
own change r, read off one column of T (or the domain order of the schema, for constants).
"""
from dataclasses import dataclass, field
from .labels import UP, DN, EQ, ID, act, flip


@dataclass(frozen=True)
class V:            # a shared child (present on both sides)
    name: str


@dataclass(frozen=True)
class F:            # a fresh subtree, sampled from G, present on one side only
    name: str
    sort: str


@dataclass(frozen=True)
class P:            # a production applied to sub-patterns
    prod: str
    kids: tuple = ()
    tag: str = ""   # for constants: "k" (Q side) or "k′" (Q′ side)


@dataclass
class NodeKind:
    kind: str                 # copy | swap | insert | drop | constant | law
    sort: str                 # the non-terminal X of G at this node
    r: str                    # own change
    q: object                 # Q-side pattern
    q2: object                # Q′-side pattern
    shared: list              # [(var, sort)] in a fixed order
    paths: dict               # var -> list of slot signs on the Q′ side, outermost first
    fresh: list = field(default_factory=list)   # [(var, sort, side)] side in {"Q", "Q′"}
    why: str = ""             # which entry of T (or the schema) justifies r
    const_rel: str = ""       # for constant kinds: ">" (k′ > k) or "<"


def _paths(pattern, g, T, prefix=()):
    """Slot signs from the root of `pattern` down to every shared variable."""
    out = {}
    if isinstance(pattern, V):
        out[pattern.name] = list(prefix)
    elif isinstance(pattern, P):
        prod = g.get(pattern.prod)
        signs = T.signs(prod.op) if prod.slots else ()
        for i, kid in enumerate(pattern.kids):
            out.update(_paths(kid, g, T, prefix + (signs[i],)))
    return out


def _var_sorts(pattern, g, sort=None, out=None):
    out = {} if out is None else out
    if isinstance(pattern, V):
        if pattern.name in out and out[pattern.name] != sort:
            raise ValueError(f"variable {pattern.name} used at two sorts")
        out[pattern.name] = sort
    elif isinstance(pattern, P):
        prod = g.get(pattern.prod)
        if sort is not None and prod.sort != sort:
            raise ValueError(f"{prod.name} has sort {prod.sort}, expected {sort}")
        for kid, s in zip(pattern.kids, prod.slots):
            _var_sorts(kid, g, s, out)
    return out


def _vars_in_order(pattern, acc=None):
    acc = [] if acc is None else acc
    if isinstance(pattern, V):
        acc.append(pattern.name)
    elif isinstance(pattern, P):
        for k in pattern.kids:
            _vars_in_order(k, acc)
    return acc


def _canon(q, q2):
    """Rename variables by first occurrence, to detect a law direction that repeats another."""
    names = {}
    for v in _vars_in_order(q) + _vars_in_order(q2):
        names.setdefault(v, f"v{len(names)}")

    def ren(p):
        if isinstance(p, V):
            return ("V", names[p.name])
        if isinstance(p, F):
            return ("F", p.sort)
        return ("P", p.prod, p.tag, tuple(ren(k) for k in p.kids))
    return ren(q), ren(q2)


def _kind(kind, g, T, sort, r, q, q2, why, fresh=(), const_rel=""):
    order = _vars_in_order(q)
    sorts = _var_sorts(q, g, sort)
    sorts2 = _var_sorts(q2, g, sort)
    if sorted(order) != sorted(_vars_in_order(q2)) or len(set(order)) != len(order):
        raise ValueError(f"{why}: not linear (each shared variable must occur once on each side)")
    if sorts != sorts2:
        raise ValueError(f"{why}: a variable changes sort between the two sides")
    return NodeKind(kind, sort, r, q, q2, [(v, sorts[v]) for v in order], _paths(q2, g, T),
                    list(fresh), why, const_rel)


def _pp(op):
    return {"<=": "≤", ">=": "≥", "<>": "≠"}.get(op, op)


def copy_kinds(g, T):
    out = []
    for p in g.productions:
        if p.op == "CONST":
            out.append(NodeKind("copy", p.sort, ID, P(p.name, (), "k"), P(p.name, (), "k"), [], {},
                                why="same constant on both sides"))
            continue
        vs = tuple(V(f"x{i + 1}") for i in range(len(p.slots)))
        out.append(_kind("copy", g, T, p.sort, ID, P(p.name, vs), P(p.name, vs), f"copy {_pp(p.op) if p.column and p.slots else p.name}"))
    return out


def swap_kinds(g, T):
    out = []
    for p in g.productions:
        for p2 in g.productions:
            if p is p2 or p.sort != p2.sort or p.slots != p2.slots:
                continue
            if p.op not in T.ops or p2.op not in T.ops or p.op == p2.op:
                continue
            if T.leq(p.op, p2.op):
                r, why = UP, f"order: {_pp(p.op)} ≼ {_pp(p2.op)}"
            elif T.leq(p2.op, p.op):
                r, why = DN, f"order: {_pp(p2.op)} ≼ {_pp(p.op)}"
            else:
                continue
            vs = tuple(V(f"x{i + 1}") for i in range(len(p.slots)))
            out.append(_kind("swap", g, T, p.sort, r, P(p.name, vs), P(p2.name, vs), why))
    return out


def insert_drop_kinds(g, T):
    """x ⇒ f(x, z) and back. The own change comes from a bound of f in x's slot
    (deflationary: f(x, ·) ⊑ x; inflationary: x ⊑ f(x, ·)), or, when T gives none, from an identity
    element e in the other slot together with that slot's sign (which implies the bound)."""
    out = []
    names = "αβγδ"
    for p in g.productions:
        if p.op not in T.ops or len(p.slots) != 2:
            continue
        signs = T.signs(p.op)
        for i in (0, 1):                               # i: slot of the shared child x; j: slot of z
            j = 1 - i
            if p.slots[i] != p.sort:
                continue                               # x and f(x, z) must have the same sort
            r_ins, why = None, None
            bound = T.bound(p.op, i)
            if bound:
                r_ins = DN if bound == "deflationary" else UP
                why = f"bound: {p.op} is {bound} in slot {names[i]}"
            for jj, value, extreme in T.identities(p.op):
                if jj != j:
                    continue
                base = UP if extreme == "least" else DN    # moving slot j from e to z
                r_id = act(signs[j], base)
                if r_ins is not None and r_id != r_ins:
                    raise ValueError(f"{p.op}: bound and identity disagree")
                r_ins = r_id
                why = (f"identity: {'∅' if value == 'EMPTY' else value} is the {extreme} value of slot "
                       f"{names[j]} of {p.op}, sign {'−' if signs[j] == '-' else signs[j]}")
            if r_ins is None:
                continue
            x, z = V("x1"), F("z", p.slots[j])
            kids = (x, z) if i == 0 else (z, x)
            out.append(_kind("insert", g, T, p.sort, r_ins, x, P(p.name, kids), why, [("z", p.slots[j], "Q′")]))
            out.append(_kind("drop", g, T, p.sort, flip(r_ins), P(p.name, kids), x, why, [("z", p.slots[j], "Q")]))
    return out


def extreme_kinds(g, T):
    """z ⇒ ⊤ and z ⇒ ⊥ (and back) for a sort whose greatest / least element is a production of G."""
    out = []
    for sort, ex in T.extremes.items():
        for which, name in ex.items():
            r = UP if which == "greatest" else DN
            z_q, z_q2 = F("z", sort), F("z", sort)
            why = f"extreme: {name} is the {which} {sort}"
            out.append(NodeKind("extreme", sort, r, z_q, P(name, ()), [], {}, [("z", sort, "Q")], why))
            out.append(NodeKind("extreme", sort, flip(r), P(name, ()), z_q2, [], {}, [("z", sort, "Q′")], why))
    return out


def constant_kinds(g):
    out = []
    for p in g.productions:
        if p.op == "CONST" and g.domains[p.domain]["ordered"]:
            for rel, r in ((">", UP), ("<", DN)):
                out.append(NodeKind("constant", p.sort, r, P(p.name, (), "k"), P(p.name, (), "k′"), [], {},
                                    why=f"domain order of {p.domain}: k′ {rel} k", const_rel=rel))
    return out


def _to_pattern(spec, subst):
    if isinstance(spec, str):
        return V(spec)
    head = subst.get(spec[0], spec[0])
    return P(head, tuple(_to_pattern(s, subst) for s in spec[1:]))


def law_instances(g, T):
    """Yield (law id, name, lhs pattern, rhs pattern) for every instance of every law in T."""
    names = {p.name for p in g.productions}
    for law in T.laws:
        if "ops" in law:
            for op in law["ops"]:
                yield law["id"], law["name"], _to_pattern(law["lhs"], {"f": op}), _to_pattern(law["rhs"], {"f": op})
        elif "instances" in law:
            for inst in law["instances"]:
                yield law["id"], law["name"], _to_pattern(inst["lhs"], {}), _to_pattern(inst["rhs"], {})
        elif "instances_from" in law:                  # explicit list generated elsewhere
            for inst in law["instances_from"]:
                yield law["id"], law["name"], _to_pattern(inst["lhs"], {}), _to_pattern(inst["rhs"], {})
        elif "pairs" in law:
            for a, b in law["pairs"]:
                for t1, t2 in ((a, b), (b, a)):
                    for col in g.domains:
                        p1, p2 = f"{t1}[{col}]", f"{t2}[{col}]"
                        if p1 in names and p2 in names:
                            yield (law["id"], law["name"], _to_pattern(law["lhs"], {"θ": p1}),
                                   _to_pattern(law["rhs"], {"θ̄": p2}))
        else:
            yield law["id"], law["name"], _to_pattern(law["lhs"], {}), _to_pattern(law["rhs"], {})


def law_kinds(g, T):
    out, seen = [], set()
    for lid, lname, lhs, rhs in law_instances(g, T):
        root = lhs if isinstance(lhs, P) else rhs
        sort = g.get(root.prod).sort
        for q, q2 in ((lhs, rhs), (rhs, lhs)):
            key = _canon(q, q2)
            if key in seen:
                continue
            seen.add(key)
            out.append(_kind("law", g, T, sort, EQ, q, q2, f"law {lid} ({lname})"))
    return out


def all_kinds(g, T):
    return (copy_kinds(g, T) + swap_kinds(g, T) + insert_drop_kinds(g, T) + extreme_kinds(g, T)
            + constant_kinds(g) + law_kinds(g, T))
