"""Robustness check for M2 (exact atoms): count atoms only in G* again after identifying mirror images
(an insert or drop on the left or right operand of a commutative operator counts as one edit), so that
G* gets no credit for e.g. dropping the first rather than the last conjunct."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import measure_gain as M          # noqa: E402

COMM = r"(UNION|UNION_ALL|INTERSECT|INTERSECT_ALL|AND_CA|AND_CAB|AND_H|OR_CA|OR_CAB|OR_H)"


def canon(atom):
    e, pol, ctx = atom
    e = re.sub(COMM + r"\((<[A-Za-z]+>), (x\d)\)", r"\1(\3, \2)", e)
    return (e, pol, ctx)


st_full = [h for h in {r.head for r in M.RULES} if h[0] == "Stmt" and h[1] != M.ID]
st_r = [("Stmt", M.UP), ("Stmt", M.DN)]
gv, gp = M.restricted("valscope"), M.restricted("pinolo")
full, _ = M.exact_atoms(M.RULES, st_full)
v, _ = M.exact_atoms(gv, st_r, lambda i, p: M.valscope_mutator(i, p) is not None)
p, _ = M.exact_atoms(gp, st_r, lambda i, p_: M.pinolo_mutator(i, p_) is not None)
cf, cv, cp = ({canon(a) for a in s} for s in (full, v, p))
nonlaw = lambda s: {a for a in s if not a[0].startswith("law")}
res = dict(raw=dict(G=len(full), V=len(v), P=len(p), only_G=len(full - v - p), only_G_nonlaw=len(nonlaw(full - v - p))),
           mirrors_identified=dict(G=len(cf), V=len(cv), P=len(cp), only_G=len(cf - cv - cp),
                                   only_G_nonlaw=len(nonlaw(cf - cv - cp))))
print(json.dumps(res, indent=1))
(ROOT / "outputs" / "mysql" / "measures" / "M2_exact_mirror_check.json").write_text(json.dumps(res, indent=1))
