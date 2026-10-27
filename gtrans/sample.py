"""Sampling from G (fresh subtrees) and from G* (pairs Q, Q′ with metRel)."""
import random
from .kinds import V, F, P
from .semantics import build


class Sampler:
    def __init__(self, g, rules, seed=0, builder=build, weight=None):
        self.g, self.rng, self.build = g, random.Random(seed), builder
        self.weight = weight or (lambda rule: 1.0)
        self.by_head = {}
        for r in rules:
            self.by_head.setdefault(r.head, []).append(r)
        self.h_sort = self._g_heights()
        self.h_head = self._gstar_heights()

    # ---- minimal derivation heights, used to stop recursion at a depth budget
    def _g_heights(self):
        h, changed = {}, True
        while changed:
            changed = False
            for p in self.g.productions:
                if all(s in h for s in p.slots):
                    v = 1 + max((h[s] for s in p.slots), default=0)
                    if v < h.get(p.sort, 10 ** 9):
                        h[p.sort] = v
                        changed = True
        return h

    def rule_height(self, r, h):
        parts = [h.get(c, 10 ** 9) for c in r.children] + [self.h_sort[s] for (_, s, _) in r.kind.fresh]
        return 1 + max(parts, default=0)

    def _gstar_heights(self):
        h, changed = {}, True
        while changed:
            changed = False
            for head, rs in self.by_head.items():
                v = min(self.rule_height(r, h) for r in rs)
                if v < h.get(head, 10 ** 9):
                    h[head] = v
                    changed = True
        return h

    # ---- G: fresh subtrees
    def const_value(self, domain, rel=None, k=None):
        d = self.g.domains[domain]
        if "values" in d:
            return self.rng.choice(d["values"])
        lo, hi = d["min"], d["max"]
        if rel == ">":
            return self.rng.randint(k + 1, hi)
        if rel == "<":
            return self.rng.randint(lo, k - 1)
        return self.rng.randint(lo, hi)

    def sample_g(self, sort, budget):
        prods = [p for p in self.g.by_sort(sort) if 1 + max((self.h_sort[s] for s in p.slots), default=0) <= max(budget, self.h_sort[sort])]
        p = self.rng.choice(prods)
        kids = [self.sample_g(s, budget - 1) for s in p.slots]
        return self.build(p, kids, self.const_value(p.domain) if p.op == "CONST" else None)

    # ---- G*: pairs
    def sample_pair(self, head, budget, trace=None, depth=0):
        """Return (Q-side tree, Q′-side tree) derived from the labelled non-terminal `head`."""
        cands = [r for r in self.by_head[head] if self.rule_height(r, self.h_head) <= max(budget, self.h_head[head])]
        r = self.rng.choices(cands, weights=[self.weight(c) for c in cands])[0]
        if trace is not None:
            trace.append((depth, r))
        K = r.kind
        env = {v: self.sample_pair((s, l), budget - 1, trace, depth + 1) for (v, s), l in zip(K.shared, r.labels)}
        fresh = {name: self.sample_g(s, budget - 1) for (name, s, _) in K.fresh}
        consts = {}
        if K.kind in ("copy", "constant") and isinstance(K.q, P) and self.g.get(K.q.prod).op == "CONST":
            col = self.g.get(K.q.prod).domain
            if K.kind == "constant":
                d = self.g.domains[col]
                k = self.rng.randint(d["min"], d["max"] - 1) if K.const_rel == ">" else self.rng.randint(d["min"] + 1, d["max"])
                consts = {"k": k, "k′": self.const_value(col, K.const_rel, k)}
            else:
                consts = {"k": self.const_value(col)}

        def inst(pat, side):
            if isinstance(pat, V):
                return env[pat.name][side]
            if isinstance(pat, F):
                return fresh[pat.name]
            prod = self.g.get(pat.prod)
            return self.build(prod, [inst(k, side) for k in pat.kids], consts.get(pat.tag))
        return inst(K.q, 0), inst(K.q2, 1)
