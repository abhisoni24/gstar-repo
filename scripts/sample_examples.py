"""Print sampled (Q, Q′, metRel) triples with their G* derivations, evaluated on the People table of Figure 1.

Usage: python scripts/sample_examples.py [n_per_label] [max_depth] [seed]
"""
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gtrans.model import load_grammar, load_table                       # noqa: E402
from gtrans.core import build                                            # noqa: E402
from gtrans.sample import Sampler                                        # noqa: E402
from gtrans.semantics import eval_query, column_index, show_query, sql_query   # noqa: E402
from gtrans.writer import rule_text                                      # noqa: E402
from gtrans.labels import UP, DN, EQ                                     # noqa: E402

FIGURE1 = {"People": [("Ann", 30, "Chicago"), ("Bob", 17, "Chicago"), ("Cal", 45, "Madison"),
                      ("Dee", 22, "Madison"), ("Fay", 52, "Chicago")]}
REL = {UP: "⊆", DN: "⊇", EQ: "="}


def main(n=4, max_depth=3, seed=7, lang="tinyq"):
    n, max_depth, seed = int(n), int(max_depth), int(seed)
    inp, out = ROOT / "inputs" / lang, ROOT / "outputs" / lang
    schema = json.loads((inp / "schema.json").read_text())
    g = load_grammar(inp / "grammar.json", inp / "schema.json")
    T = load_table(inp / "table_T.json")
    _, rules, _ = build(g, T)
    s = Sampler(g, rules, seed)
    rng = random.Random(seed)
    cols = column_index(schema)
    lines = [f"Sampled triples (Q, Q′, metRel) from G* for {lang}, evaluated on the People table of Figure 1.",
             "Each derivation lists the G* rules used, top-down; indentation shows the depth.", ""]
    k = 0
    for lab in (UP, DN, EQ):
        got = 0
        while got < n:
            trace = []
            q, q2 = s.sample_pair((g.start, lab), rng.randint(max(2, max_depth - 1), max_depth), trace)
            if q == q2:
                continue
            got += 1
            k += 1
            names = lambda res: ", ".join(sorted(r[0] for r in res)) or "(none)"
            lines += [f"#{k}  start {g.start}[{lab}]  so metRel(Q, Q′) is {REL[lab]}", "  derivation:"]
            for depth, r in trace:
                lhs, body, where, calc, why = rule_text(r, g)
                lines.append(f"    {'  ' * depth}{lhs} → {body}     [{r.kind.kind}; {why}]")
            lines += [f"  Q  = {show_query(q)}", f"  Q′ = {show_query(q2)}",
                      f"  on Figure 1:  Q → {names(eval_query(q, FIGURE1, cols))};  "
                      f"Q′ → {names(eval_query(q2, FIGURE1, cols))}",
                      f"  SQL Q : {sql_query(q)}", f"  SQL Q′: {sql_query(q2)}", ""]
    (out / "samples.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:60]))


if __name__ == "__main__":
    main(*sys.argv[1:])
