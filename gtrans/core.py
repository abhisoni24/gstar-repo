"""GTrans(G, T): build the test grammar G* (Section 5 of the note), then reduce it."""
import itertools
from dataclasses import dataclass
from .labels import LABELS, TOP, UP, DN, EQ, ID, act_path, compose_all, sign_product
from .kinds import all_kinds


@dataclass
class Rule:
    head: tuple            # (X, ℓ)
    kind: object           # the NodeKind
    labels: tuple          # ℓ_1 … ℓ_m for the shared children, in kind.shared order
    terms: tuple           # (σ′_i ⊗ ℓ_i) for display

    @property
    def children(self):
        return [(s, l) for (_, s), l in zip(self.kind.shared, self.labels)]


def gtrans(g, T):
    """For each node kind K at X and each choice of child labels, add X_ℓ → K(...) when ℓ ≠ ?."""
    rules = []
    for K in all_kinds(g, T):
        m = len(K.shared)
        for labs in itertools.product(LABELS, repeat=m):
            terms = tuple(act_path(K.paths[v], l) for (v, _), l in zip(K.shared, labs))
            ell = compose_all((K.r,) + terms)
            if ell != TOP:
                rules.append(Rule((K.sort, ell), K, labs, terms))
    return rules


def reduce_gstar(rules, starts):
    """Keep only rules whose labelled children derive something (productive) and that are reachable."""
    productive, changed = set(), True
    while changed:
        changed = False
        for r in rules:
            if r.head not in productive and all(c in productive for c in r.children):
                productive.add(r.head)
                changed = True
    kept = [r for r in rules if r.head in productive and all(c in productive for c in r.children)]
    reach, todo = set(), [s for s in starts if s in productive]
    reach.update(todo)
    by_head = {}
    for r in kept:
        by_head.setdefault(r.head, []).append(r)
    while todo:
        h = todo.pop()
        for r in by_head.get(h, []):
            for c in r.children:
                if c not in reach:
                    reach.add(c)
                    todo.append(c)
    kept = [r for r in kept if r.head in reach]
    return kept, productive, reach


def build(g, T):
    raw = gtrans(g, T)
    starts = [(g.start, UP), (g.start, DN), (g.start, EQ)]
    kept, productive, reach = reduce_gstar(raw, starts)
    return raw, kept, starts


def path_sign(K, var):
    return sign_product(K.paths[var])
