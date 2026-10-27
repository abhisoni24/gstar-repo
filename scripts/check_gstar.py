"""Sample pairs from G* and check metRel on random databases, with the reference evaluator and SQLite.

Usage: python scripts/check_gstar.py [n_pairs_per_label] [n_databases] [max_depth] [seed]
"""
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gtrans.model import load_grammar, load_table                        # noqa: E402
from gtrans.core import build                                             # noqa: E402
from gtrans.sample import Sampler                                         # noqa: E402
from gtrans.semantics import (random_db, column_index, sqlite_connect,    # noqa: E402
                              sqlite_eval, eval_query, show_query, sql_query)
from gtrans.labels import UP, DN, EQ                                      # noqa: E402

HOLDS = {UP: lambda a, b: a <= b, DN: lambda a, b: a >= b, EQ: lambda a, b: a == b}
REL = {UP: "⊆", DN: "⊇", EQ: "="}


def main(n=3000, n_db=60, max_depth=5, seed=1, lang="tinyq"):
    n, n_db, max_depth, seed = int(n), int(n_db), int(max_depth), int(seed)
    inp, out = ROOT / "inputs" / lang, ROOT / "outputs" / lang
    schema = json.loads((inp / "schema.json").read_text())
    g = load_grammar(inp / "grammar.json", inp / "schema.json")
    T = load_table(inp / "table_T.json")
    _, rules, _ = build(g, T)
    s = Sampler(g, rules, seed)
    rng = random.Random(seed + 1)
    dbs = [random_db(schema, rng) for _ in range(n_db)]
    cons = [sqlite_connect(schema, d) for d in dbs]
    cols = column_index(schema)
    stats, failures, kinds_used = Counter(), [], Counter()
    t0 = time.time()
    for lab in (UP, DN, EQ):
        for i in range(n):
            trace = []
            q, q2 = s.sample_pair((g.start, lab), rng.randint(1, max_depth), trace)
            for _, r in trace:
                kinds_used[r.kind.kind] += 1
            if q == q2:
                stats[f"identical text dropped ({REL[lab]})"] += 1
                continue
            stats[f"pairs checked ({REL[lab]})"] += 1
            for db, con in zip(dbs, cons):
                a, b = eval_query(q, db, cols), eval_query(q2, db, cols)
                sa, sb = sqlite_eval(con, q), sqlite_eval(con, q2)
                if a != sa or b != sb:
                    stats["evaluator disagreements"] += 1
                    failures.append(("evaluator", lab, show_query(q), show_query(q2), sql_query(q)))
                    break
                if not HOLDS[lab](a, b):
                    stats["broken relations"] += 1
                    failures.append(("relation", lab, show_query(q), show_query(q2), db))
                    break
    dt = time.time() - t0
    lines = [f"Check of G* for {lang}: {n} samples per start symbol, depth budget 1..{max_depth}, "
             f"{n_db} random databases, seed {seed}, {dt:.1f} s", ""]
    lines += [f"{k}: {v}" for k, v in sorted(stats.items())]
    lines += ["", "rules used, by kind: " + ", ".join(f"{k} {v}" for k, v in sorted(kinds_used.items()))]
    lines += ["", f"failures: {len(failures)}"] + [repr(f) for f in failures[:20]]
    (out / "check_report.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main(*sys.argv[1:])
