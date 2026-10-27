"""Write G* in a readable text form, as JSON, and a summary of the counts."""
import json
from collections import Counter, OrderedDict
from .kinds import V, F, P
from .labels import LABELS, sign_product
from .semantics import PRETTY

KIND_ORDER = ["copy", "swap", "insert", "drop", "extreme", "constant", "law"]


def show_pattern(pat, g, top=True):
    if isinstance(pat, V):
        return pat.name
    if isinstance(pat, F):
        return pat.name
    prod = g.get(pat.prod)
    if prod.op == "CONST":
        return pat.tag
    if not prod.slots:
        return prod.print_fmt
    fmt = prod.print_fmt
    for op, pretty in PRETTY.items():
        fmt = fmt.replace(f" {op} ", f" {pretty} ")
    kids = [show_pattern(k, g, False) for k in pat.kids]
    s = fmt.format(*kids)
    return s if top else f"({s})"


def _s(sign):
    return "−" if sign == "-" else sign


def head_str(head):
    return f"{head[0]}[{head[1]}]"


def rule_text(r, g):
    K = r.kind
    lhs = head_str(r.head)
    q, q2 = show_pattern(K.q, g), show_pattern(K.q2, g)
    body = q if K.kind == "copy" else f"{q}  ⇒  {q2}"
    if K.kind == "constant":
        body += f"   with k′ {K.const_rel} k"
    where = [f"{v}: {s}[{l}]" for (v, s), l in zip(K.shared, r.labels)]
    where += [f"{n}: {s} (fresh, {side} side only)" for (n, s, side) in K.fresh]
    terms = [f"({_s(sign_product(K.paths[v]))}⊗{l})" for (v, _), l in zip(K.shared, r.labels)]
    r0 = "(=)" if K.r == "=" else K.r
    calc = " ∘ ".join([r0] + terms) if K.kind != "copy" else (" ∘ ".join(terms) if terms else "id")
    return lhs, body, ", ".join(where), f"{calc} = {r.head[1]}", K.why


def head_order(heads, g):
    sorts = [g.start, g.pred_sort] + sorted({h[0] for h in heads} - {g.start, g.pred_sort})
    lab = {l: i for i, l in enumerate(["↑", "↓", "=", "id"])}
    return sorted(heads, key=lambda h: (sorts.index(h[0]), lab[h[1]]))


def write_text(path, rules, raw, g, title):
    by_head = OrderedDict()
    for h in head_order({r.head for r in rules}, g):
        by_head[h] = [r for r in rules if r.head == h]
    kinds = Counter(r.kind.kind for r in rules)
    lines = [title, "=" * len(title), "",
             "Notation. X[ℓ] is the labelled non-terminal X_ℓ of the note. A rule reads",
             "    X[ℓ] → u  ⇒  u′      where x1: Y1[ℓ1], …     ℓ = r ∘ (σ′1⊗ℓ1) ∘ … = ℓ",
             "u is what the rule adds to the gold query Q, u′ what it adds to the mutant query Q′.",
             "A copy rule has u = u′ and shows u once. Shared children x1, x2, … appear on both sides; a fresh",
             "subtree z is sampled from G and appears on one side only. k and k′ are constants of the column.",
             "Start symbols: " + ", ".join(head_str((g.start, l)) for l in ("↑", "↓", "=")) +
             "   (metRel(Q, Q′) = ⊆, ⊇, = respectively).", "",
             f"Rules after reduction: {len(rules)}   (before reduction: {len(raw)})",
             "By kind: " + ", ".join(f"{k} {kinds[k]}" for k in KIND_ORDER), "",
             "Contents (rules per labelled non-terminal):"]
    for h, rs in by_head.items():
        c = Counter(r.kind.kind for r in rs)
        lines.append(f"  {head_str(h):<16} {len(rs):>5}   " + ", ".join(f"{k} {c[k]}" for k in KIND_ORDER if c[k]))
    for h, rs in by_head.items():
        lines += ["", "-" * 100, f"{head_str(h)}   ({len(rs)} rules)", "-" * 100]
        for kind in KIND_ORDER:
            sub = [r for r in rs if r.kind.kind == kind]
            if not sub:
                continue
            lines += ["", f"  [{kind}]  {len(sub)} rules"]
            for r in sub:
                lhs, body, where, calc, why = rule_text(r, g)
                lines.append(f"    {lhs} → {body}")
                if where:
                    lines.append(f"        where {where}")
                lines.append(f"        ℓ = {calc}        [{why}]")
    path.write_text("\n".join(lines) + "\n")


def write_json(path, rules, g):
    out = []
    for r in rules:
        K = r.kind
        out.append({
            "head": {"nonterminal": r.head[0], "label": r.head[1]},
            "kind": K.kind, "own_change": K.r, "justification": K.why,
            "q_side": show_pattern(K.q, g), "q2_side": show_pattern(K.q2, g),
            "shared": [{"var": v, "sort": s, "label": l, "q2_path_sign": sign_product(K.paths[v])}
                       for (v, s), l in zip(K.shared, r.labels)],
            "fresh": [{"var": n, "sort": s, "side": side} for (n, s, side) in K.fresh],
            "constant_relation": K.const_rel or None,
        })
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1))


def summary(rules, raw, g, kinds):
    c_raw, c_kept = Counter(r.kind.kind for r in raw), Counter(r.kind.kind for r in rules)
    c_k = Counter(K.kind for K in kinds)
    heads_raw = {r.head for r in raw}
    heads_kept = {r.head for r in rules}
    lines = ["| kind | node kinds | rules from GTrans | rules after reduction |", "|---|---|---|---|"]
    for k in KIND_ORDER:
        lines.append(f"| {k} | {c_k[k]} | {c_raw[k]} | {c_kept[k]} |")
    lines.append(f"| total | {sum(c_k.values())} | {len(raw)} | {len(rules)} |")
    removed = sorted(heads_raw - heads_kept, key=str)
    return "\n".join(lines), removed
