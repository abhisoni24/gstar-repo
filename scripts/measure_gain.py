"""Measure what G* for MySQL adds over ValScope and Pinolo.

M1  Edit inventory: the difference kinds of G* (an edit plus where it may occur) mapped to ValScope's 26 and
    Pinolo's mutators, in both directions.
M2  Pair-shape coverage: sample pairs from G*, from G*_V (G* restricted to ValScope's inventory and to one edit
    per pair) and from G*_P (G* restricted to Pinolo's inventory, no edit inside a changed node, no = labels);
    compare the distinct shapes. A shape is the family, the label, and for every difference node its edit, its
    polarity (product of signs from the root) and the classes of context it sits in (NOT, EXCEPT-right, EXISTS,
    aggregate, HAVING, ON, derived table, set operation, ...).
M3  Out of reach: for each pair sampled from G*, can ValScope (one mutation from its inventory, at a place its
    mutator allows) or Pinolo (any number of its mutators, none inside another, no equivalences, rows only)
    produce it from the same gold query? Reported with and without their grammar limits.

Usage: python scripts/measure_gain.py N_PAIRS MAX_DEPTH SEED OUTDIR
"""
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gtrans.model import load_grammar_explicit, load_table       # noqa: E402
from gtrans.core import build, reduce_gstar                       # noqa: E402
from gtrans.kinds import V, F, P                                  # noqa: E402
from gtrans.labels import ID, EQ, UP, DN, sign_product            # noqa: E402
from gtrans.sample import Sampler                                 # noqa: E402
from gtrans.sqlexec import builder                                # noqa: E402

INP = ROOT / "inputs" / "mysql"
G = load_grammar_explicit(INP / "grammar.json")
T = load_table(INP / "table_T.json")
RAW, RULES, STARTS = build(G, T)
OPN = lambda name: G.get(name).op
CLAUSE_WHERE = {("SEL", 1), ("SELD", 1), ("DSEL", 1), ("DSELD", 1)} | {(f"J{d}SEL_{k}", 3) for d in ("", "D") for k in ("INNER", "LEFT", "RIGHT")}
CLAUSE_ON = {(f"J{d}SEL_{k}", 2) for d in ("", "D") for k in ("INNER", "LEFT", "RIGHT")}
CLAUSE_HAVING = {("GSEL", 1)}


# ------------------------------------------------------------------ describing an edit (a difference node kind)
def pat(p):
    if isinstance(p, V):
        return p.name
    if isinstance(p, F):
        return f"<{p.sort}>"
    if not p.kids:
        return p.prod + (f"[{p.tag}]" if p.tag else "")
    return f"{p.prod}(" + ", ".join(pat(k) for k in p.kids) + ")"


def edit_id(K):
    rel = f" (k′ {K.const_rel} k)" if K.kind == "constant" else ""
    return f"{K.kind}: {pat(K.q)} ⇒ {pat(K.q2)}{rel}"


def edit_info(K):
    """A small record used by the inventory rules below."""
    info = dict(kind=K.kind, sort=K.sort)
    if K.kind == "swap":
        info.update(a=OPN(K.q.prod), b=OPN(K.q2.prod), prod=K.q.prod)
    elif K.kind in ("insert", "drop"):
        f = K.q2 if K.kind == "insert" else K.q
        info.update(op=OPN(f.prod), xslot=[i for i, k in enumerate(f.kids) if isinstance(k, V)][0])
    elif K.kind == "extreme":
        to_ext = isinstance(K.q, F)
        e = K.q2 if to_ext else K.q
        info.update(to_extreme=to_ext, extreme=OPN(e.prod))
    elif K.kind == "constant":
        info.update(domain=G.get(K.q.prod).domain, rel=K.const_rel)
    elif K.kind == "law":
        info.update(law=K.why.split()[1])
    return info


# ------------------------------------------------------------------ ValScope's and Pinolo's inventories, as rules
VS_CMP = {(">", ">="), ("<", "<="), ("=", ">="), (">=", ">"), ("<=", "<")}
PN_CMP = {("<=", "="), (">=", "="), ("<=", "<"), (">=", ">"), ("<>", "<"), ("<>", ">")}
PN_CMP |= {(b, a) for a, b in PN_CMP}
AGG = lambda op: op.split("_", 1)[1] if op.startswith(("AGG_", "G_")) else None


def valscope_mutator(info, place):
    """Name of the ValScope mutator that makes this edit at this place, or None."""
    k = info["kind"]
    if k == "swap":
        a, b = info["a"], info["b"]
        if (a, b) in VS_CMP:
            return "FixMCmpOp"
        if {a, b} in ({"SEL", "SELD"}, {"DSEL", "DSELD"}):
            return "FixMDistinct"
        if {a, b} == {"UNION", "UNION_ALL"}:
            return "FixMUnionAll"
        if a.endswith("_INNER") and b.endswith("_LEFT"):
            return "FixMInnerJoin"
        if (a, b) == ("INTERSECT", "UNION"):
            return "FixMIntersect"
        aa, bb = AGG(a), AGG(b)
        if aa and bb:
            return {("MAX", "MIN"): "AggM_MaxToMin", ("MIN", "MAX"): "AggM_MinToMax", ("AVG", "MIN"): "AggM_AvgToMin",
                    ("AVG", "MAX"): "AggM_AvgToMax", ("CNTD", "CNT"): "AggM_CountDistinctToCount",
                    ("CNT", "CNTD"): "AggM_CountToCountDistinct"}.get((aa, bb))
        return None
    if k == "drop":
        if info["op"] == "AND" and info["xslot"] == 0:
            return "FixMLogicalAnd"
        if info["op"] == "EXCEPT" and info["xslot"] == 0:
            return "FixMExcept"
        return None
    if k == "insert":
        return "AggM_AvgAddConstant / ExprM_AddConstant" if info["op"] == "PLUS" else None
    if k == "extreme":
        if place in CLAUSE_WHERE:
            return "FixMWhere"
        if place in CLAUSE_ON:
            return "FixMOn"
        if place in CLAUSE_HAVING:
            return "FixMHaving"
        return None
    if k == "constant":
        return "ExprM_AddConstant (≈: k ⇒ k′ in a comparison equals adding k′ − k to the column)" if info["domain"] == "int" else None
    return None


def pinolo_mutator(info, place):
    k = info["kind"]
    if k == "swap":
        a, b = info["a"], info["b"]
        if (a, b) in PN_CMP:
            return "comparison"
        if {a, b} in ({"SEL", "SELD"}, {"DSEL", "DSELD"}):
            return "DISTINCT"
        if {a, b} == {"UNION", "UNION_ALL"}:
            return "UNION ALL / UNION"
        if {a, b} == {"INTERSECT", "UNION"}:
            return "UNION / INTERSECT"
        if {a, b} == {"FALSE", "TRUE"}:
            return "predicate to TRUE / FALSE"
        return None
    if k in ("insert", "drop"):
        if info["op"] == "EXCEPT" and info["xslot"] == 0:
            return "r ⇔ r MINUS r′"
        return None
    if k == "extreme":
        return "predicate to TRUE / FALSE" if info["sort"] in ("CA", "CAB") else None
    if k == "constant":
        return "BETWEEN (unverified)" if place and place[0].startswith("BETW") else None
    return None


# ------------------------------------------------------------------ pair trees from sampling traces
def var_path(pattern, var, prefix=()):
    if isinstance(pattern, V):
        return list(prefix) if pattern.name == var else None
    if isinstance(pattern, P):
        for i, k in enumerate(pattern.kids):
            r = var_path(k, var, prefix + ((pattern.prod, i),))
            if r is not None:
                return r
    return None


def tree(trace):
    nodes, stack = [], []
    for depth, r in trace:
        n = dict(rule=r, depth=depth, kids=[], path=[])
        while stack and stack[-1]["depth"] >= depth:
            stack.pop()
        if stack:
            par = stack[-1]
            var = par["rule"].kind.shared[len(par["kids"])][0]
            n["path"] = par["path"] + var_path(par["rule"].kind.q2, var)
            par["kids"].append(n)
        nodes.append(n)
        stack.append(n)
    return nodes


def slot_sign(prod, slot):
    op = OPN(prod)
    return T.signs(op)[slot] if op in T.ops and T.signs(op) else "+"


CLASS = [(lambda p, s: OPN(p) == "NOT", "NOT"), (lambda p, s: p in ("EXCEPT", "EXCEPT_ALL") and s == 1, "EXCEPT-right"),
         (lambda p, s: p == "EXISTS_CA", "EXISTS"), (lambda p, s: p.startswith("AGG_"), "aggregate"),
         (lambda p, s: p == "GSEL" and s == 1, "HAVING"), (lambda p, s: p == "GSEL" and s == 0, "grouped input"),
         (lambda p, s: (p, s) in CLAUSE_ON, "ON"), (lambda p, s: p.startswith("JDSEL") and s < 2, "join operand"),
         (lambda p, s: p in ("DSEL", "DSELD") and s == 0, "derived table"),
         (lambda p, s: OPN(p) in ("UNION", "UNION_ALL", "INTERSECT", "INTERSECT_ALL", "EXCEPT", "EXCEPT_ALL"), "set operation"),
         (lambda p, s: p == "PLUS", "arithmetic")]


def describe(trace):
    nodes = tree(trace)
    fam = {"STMT_Q": "rows", "STMT_V": "value", "STMT_G": "groups"}[nodes[0]["rule"].kind.q.prod]
    diffs = []
    for n in nodes:
        K = n["rule"].kind
        if K.kind == "copy":
            continue
        path = n["path"]
        pol = sign_product([slot_sign(p, s) for p, s in path])
        ctx = frozenset(c for p, s in path for f, c in CLASS if f(p, s))
        place = path[-1] if path else None
        info = edit_info(K)
        diffs.append(dict(edit=edit_id(K), info=info, polarity=pol, context=ctx, place=place,
                          child_labels=n["rule"].labels, label=n["rule"].head[1]))
    return fam, nodes[0]["rule"].head[1], diffs


def shape(fam, label, diffs):
    return (fam, label, tuple(sorted((d["edit"], d["polarity"], tuple(sorted(d["context"]))) for d in diffs)))


def uses(nodes_text):
    return nodes_text


# ------------------------------------------------------------------ reachability (M3)
NOT_IN_VALSCOPE_GRAMMAR = ("INTERSECT_ALL", "EXCEPT_ALL")
NOT_IN_PINOLO_GRAMMAR = ("INTERSECT_ALL", "EXCEPT_ALL", "GSEL", "AGG_", "G_", "EXISTS", "PLUS", "BETW")


def productions_used(*trees):
    out, stack = set(), list(trees)
    while stack:
        name, kids, _ = stack.pop()
        out.add(name)
        stack.extend(kids)
    return out


def reach(fam, label, diffs, prods, strict):
    """Return (valscope_ok, valscope_reason, pinolo_ok, pinolo_reason)."""
    vs_ok, vs_why = True, ""
    if len(diffs) != 1:
        vs_ok, vs_why = False, "more than one edit"
    elif any(d["info"]["kind"] == "law" for d in diffs) or label == EQ:
        vs_ok, vs_why = False, "equivalence edit (law)"
    elif valscope_mutator(diffs[0]["info"], diffs[0]["place"]) is None:
        vs_ok, vs_why = False, "edit not in ValScope's inventory (or not at a place it mutates)"
    elif strict and any(p.startswith(NOT_IN_VALSCOPE_GRAMMAR) for p in prods):
        vs_ok, vs_why = False, "construct outside ValScope's grammar"
    pn_ok, pn_why = True, ""
    if label == EQ or any(d["info"]["kind"] == "law" for d in diffs):
        pn_ok, pn_why = False, "equivalence edit (law)"
    elif any(pinolo_mutator(d["info"], d["place"]) is None for d in diffs):
        pn_ok, pn_why = False, "edit not in Pinolo's inventory"
    elif any(any(l != ID for l in d["child_labels"]) for d in diffs):
        pn_ok, pn_why = False, "edit inside a changed node"
    elif strict and (fam != "rows" or any(p.startswith(NOT_IN_PINOLO_GRAMMAR) for p in prods)):
        pn_ok, pn_why = False, "construct outside Pinolo's grammar"
    return vs_ok, vs_why, pn_ok, pn_why


# ------------------------------------------------------------------ exact atoms: every (edit, polarity, context) a grammar can produce
def exact_atoms(rules, starts, place_ok=None):
    """Propagate (context classes, polarity, place) from the start symbols through the rules; every
    difference rule reached gives an atom. Exact for the grammar, unlike sampling."""
    by_head = {}
    for r in rules:
        by_head.setdefault(r.head, []).append(r)
    seen, todo, atoms = set(), [(s, frozenset(), "+", None) for s in starts], set()
    while todo:
        st = todo.pop()
        if st in seen:
            continue
        seen.add(st)
        head, ctx, pol, place = st
        for r in by_head.get(head, []):
            K = r.kind
            if K.kind != "copy":
                info = edit_info(K)
                if place_ok is None or place_ok(info, place):
                    atoms.add((edit_id(K), pol, tuple(sorted(ctx))))
            for (var, sort), lab in zip(K.shared, r.labels):
                path = var_path(K.q2, var)
                nctx = ctx | frozenset(c for p, sl in path for f, c in CLASS if f(p, sl))
                npol = sign_product([pol] + [slot_sign(p, sl) for p, sl in path])
                todo.append(((sort, lab), nctx, npol, path[-1] if path else place))
    return atoms, len(seen)


# ------------------------------------------------------------------ restricted grammars for M2
def restricted(tool):
    keep = []
    for r in RULES:
        K = r.kind
        labels = (r.head[1],) + tuple(r.labels)
        if EQ in labels:
            continue
        if K.kind == "copy":
            if tool == "valscope" and sum(l != ID for l in r.labels) > 1:
                continue
            keep.append(r)
            continue
        if any(l != ID for l in r.labels):
            continue
        info = edit_info(K)
        ok = (valscope_mutator(info, ("SEL", 1)) or valscope_mutator(info, ("GSEL", 1)) or valscope_mutator(info, ("JSEL_INNER", 2))) \
            if tool == "valscope" else pinolo_mutator(info, ("BETW_CA", 1))
        if ok:
            keep.append(r)
    starts = [("Stmt", UP), ("Stmt", DN)]
    kept, _, _ = reduce_gstar(keep, starts)
    return kept


def sample(rules, n, depth, seed, accept=None):
    s = Sampler(G, rules, seed, builder=builder)
    rng = random.Random(seed)
    heads = sorted({r.head for r in rules if r.head[0] == "Stmt"}, key=str)
    out, tries = [], 0
    while len(out) < n and tries < 50 * n:
        tries += 1
        lab = heads[len(out) % len(heads)]
        trace = []
        q, q2 = s.sample_pair(lab, rng.randint(2, depth), trace)
        if q == q2:
            continue
        fam, label, diffs = describe(trace)
        if accept and not accept(diffs):
            continue
        out.append((fam, label, diffs, productions_used(q, q2)))
    return out


def main(n=6000, depth=5, seed=7, outdir="outputs/mysql/measures"):
    n, depth, seed = int(n), int(depth), int(seed)
    out = ROOT / outdir
    out.mkdir(parents=True, exist_ok=True)
    report = {}

    # ---------------- M1: edit inventory
    kinds = {}
    for r in RULES:
        if r.kind.kind != "copy":
            kinds.setdefault(edit_id(r.kind), r.kind)
    inv = []
    for eid, K in sorted(kinds.items()):
        info = edit_info(K)
        vs = sorted({m for m in (valscope_mutator(info, pl) for pl in list(CLAUSE_WHERE | CLAUSE_ON | CLAUSE_HAVING) + [None]) if m})
        pn = sorted({m for m in (pinolo_mutator(info, pl) for pl in [None, ("BETW_CA", 1)]) if m})
        inv.append(dict(edit=eid, kind=K.kind, sort=K.sort, own_change=K.r, why=K.why,
                        valscope=vs, pinolo=pn))
    by_kind = Counter(e["kind"] for e in inv)
    none_ = [e for e in inv if not e["valscope"] and not e["pinolo"]]
    report["M1"] = dict(edit_types_in_Gstar=len(inv), by_kind=dict(by_kind),
                        mapped_to_valscope=sum(bool(e["valscope"]) for e in inv),
                        mapped_to_pinolo=sum(bool(e["pinolo"]) for e in inv),
                        in_neither=len(none_), in_neither_by_kind=dict(Counter(e["kind"] for e in none_)))
    (out / "M1_edit_inventory.json").write_text(json.dumps(inv, indent=1, ensure_ascii=False))

    # ---------------- M2 and M3: sampling
    full = sample(RULES, n, depth, seed)
    gv = restricted("valscope")
    vs_place_ok = lambda diffs: all(valscope_mutator(d["info"], d["place"]) for d in diffs)
    vsamp = sample(gv, n, depth, seed + 1, accept=vs_place_ok)
    gp = restricted("pinolo")
    pn_place_ok = lambda diffs: all(pinolo_mutator(d["info"], d["place"]) for d in diffs)
    psamp = sample(gp, n, depth, seed + 2, accept=pn_place_ok)
    shapes = {name: {shape(f, l, d) for f, l, d, _ in smp} for name, smp in (("G*", full), ("G*_V", vsamp), ("G*_P", psamp))}
    atoms = {name: {(d["edit"], d["polarity"], tuple(sorted(d["context"]))) for _, _, ds, _ in smp for d in ds}
             for name, smp in (("G*", full), ("G*_V", vsamp), ("G*_P", psamp))}
    edits_used = {name: {d["edit"] for _, _, ds, _ in smp for d in ds} for name, smp in (("G*", full), ("G*_V", vsamp), ("G*_P", psamp))}

    def stats(smp):
        k = Counter(len(ds) for _, _, ds, _ in smp)
        return dict(pairs=len(smp),
                    edits_per_pair={str(i): k[i] for i in sorted(k)},
                    with_two_or_more_edits=round(sum(v for i, v in k.items() if i >= 2) / len(smp), 3),
                    with_an_edit_under_negative_polarity=round(sum(any(d["polarity"] == "-" for d in ds) for _, _, ds, _ in smp) / len(smp), 3),
                    with_a_law=round(sum(any(d["info"]["kind"] == "law" for d in ds) for _, _, ds, _ in smp) / len(smp), 3),
                    with_mixed_law_and_direction=round(sum(any(d["info"]["kind"] == "law" for d in ds) and l != EQ for _, l, ds, _ in smp) / len(smp), 3),
                    by_family=dict(Counter(f for f, _, _, _ in smp)))
    st_full = [h for h in {r.head for r in RULES} if h[0] == "Stmt" and h[1] != ID]
    st_r = [("Stmt", UP), ("Stmt", DN)]
    ex_full, n_full = exact_atoms(RULES, st_full)
    ex_v, n_v = exact_atoms(gv, st_r, lambda i, p: valscope_mutator(i, p) is not None)
    ex_p, n_p = exact_atoms(gp, st_r, lambda i, p: pinolo_mutator(i, p) is not None)
    report["M2_exact"] = {
        "atoms": {"G*": len(ex_full), "G*_V": len(ex_v), "G*_P": len(ex_p)},
        "propagation_states": {"G*": n_full, "G*_V": n_v, "G*_P": n_p},
        "G*_V_subset_of_G*": ex_v <= ex_full, "G*_P_subset_of_G*": ex_p <= ex_full,
        "only_in_G*": len(ex_full - ex_v - ex_p),
        "only_in_G*_without_law_atoms": len({a for a in ex_full - ex_v - ex_p if not a[0].startswith("law")}),
        "only_in_G*_by_kind": dict(Counter(a[0].split(":")[0] for a in ex_full - ex_v - ex_p)),
        "in_G*_V_or_G*_P": len(ex_v | ex_p),
    }
    (out / "M2_exact_atoms_only_in_Gstar.txt").write_text(
        "\n".join(f"{e} | polarity {p} | context {', '.join(c) or '-'}" for e, p, c in sorted(ex_full - ex_v - ex_p)) + "\n")
    report["M2"] = {
        "grammar_sizes": {"G*": len(RULES), "G*_V": len(gv), "G*_P": len(gp)},
        "samples": {"G*": stats(full), "G*_V": stats(vsamp), "G*_P": stats(psamp)},
        "distinct_shapes": {k: len(v) for k, v in shapes.items()},
        "distinct_edit_context_polarity_atoms": {k: len(v) for k, v in atoms.items()},
        "distinct_edits_used": {k: len(v) for k, v in edits_used.items()},
        "atoms_only_in_G*": len(atoms["G*"] - atoms["G*_V"] - atoms["G*_P"]),
        "atoms_of_restricted_not_seen_in_G*_sample": {k: len(atoms[k] - atoms["G*"]) for k in ("G*_V", "G*_P")},
        "context_classes_seen": {k: dict(Counter(c for _, _, ds, _ in smp for d in ds for c in d["context"]))
                                 for k, smp in (("G*", full), ("G*_V", vsamp), ("G*_P", psamp))},
    }

    # ---------------- M3: out of reach
    res = {}
    subsets = {"all pairs": lambda ds: True,
               "pairs without a law": lambda ds: not any(d["info"]["kind"] == "law" for d in ds),
               "pairs with exactly one edit": lambda ds: len(ds) == 1}
    for strict in (False, True):
        key = "with their grammar limits" if strict else "same grammar (generous)"
        res[key] = {}
        for sname, sel in subsets.items():
            sub = [x for x in full if sel(x[2])]
            if not sub:
                continue
            c, reasons_v, reasons_p = Counter(), Counter(), Counter()
            for f, l, ds, prods in sub:
                vo, vw, po, pw = reach(f, l, ds, prods, strict)
                c["valscope"] += vo
                c["pinolo"] += po
                c["either"] += vo or po
                if not vo:
                    reasons_v[vw] += 1
                if not po:
                    reasons_p[pw] += 1
            res[key][sname] = dict(
                pairs=len(sub),
                reachable_by_valscope=round(c["valscope"] / len(sub), 3),
                reachable_by_pinolo=round(c["pinolo"] / len(sub), 3),
                out_of_reach_of_both=round(1 - c["either"] / len(sub), 3),
                why_not_valscope=dict(reasons_v.most_common()), why_not_pinolo=dict(reasons_p.most_common()))
    report["M3"] = res
    (out / "measures.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
    # a few example atoms only in G*
    ex = sorted(atoms["G*"] - atoms["G*_V"] - atoms["G*_P"])[:60]
    (out / "M2_atoms_only_in_Gstar_examples.txt").write_text("\n".join(f"{e} | polarity {p} | context {c}" for e, p, c in ex) + "\n")
    print(json.dumps(report, indent=1, ensure_ascii=False)[:6000])


if __name__ == "__main__":
    main(*sys.argv[1:])
