"""Triage run A after the fact (its summary step had crashed): regenerate the pairs (same seed, deterministic),
judge each recorded violation with the reference evaluator, reduce it, and write runA/summary.json.

Run with the environment of run A (DuckDB 1.1.3): python scripts/triage_runA.py MYSQL_PORT
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from run_mysql import load, sample_pairs                       # noqa: E402
from reduce_case import Case                                   # noqa: E402
from gtrans.refeval import Ref                                 # noqa: E402
from gtrans.sqlexec import Printer, DuckDB, MySQL, holds, same_result   # noqa: E402

OUT = ROOT / "outputs" / "mysql" / "runA"


def main(port):
    g, T, raw, rules = load()
    pairs, dropped = sample_pairs(g, rules, 20000, 6, 11)
    old = [json.loads(l) for l in (OUT / "pairs.jsonl").read_text().splitlines()]
    assert all(a["q"] == b["q"] and a["q2"] == b["q2"] for a, b in zip(pairs, old)), "regeneration differs"
    dbs = json.loads((OUT / "databases.json").read_text())
    viol = [json.loads(l) for l in (OUT / "violations.jsonl").read_text().splitlines() if l.strip()]
    pr, ref = Printer(g), Ref()
    engines = {"duckdb": DuckDB(), "mysql": MySQL(int(port), "mysql")}
    reduced, rows = {}, []
    for v in viol:
        p = pairs[v["pair"]]
        db = {k: [tuple(r) for r in x] for k, x in dbs[v["db"]].items()}
        ref.use("x", db)
        want = (ref.run_tree(p["tree_q"]), ref.run_tree(p["tree_q2"]))
        eng = engines["duckdb" if v["engine"] == "duckdb" else "mysql"]
        eng.use("chk", db)
        got = (eng.run(p["q"]), eng.run(p["q2"]))
        wrong = [not same_result(p["family"], a, b) for a, b in zip(got, want)]
        side = "tree_q" if wrong[0] else "tree_q2"
        key = (v["engine"].split("-")[0], p["q"] if side == "tree_q" else p["q2"])
        if key not in reduced:
            t, d = Case(g, eng, Printer.family).reduce(p[side], db)
            reduced[key] = (pr.sql(t), {k: x for k, x in d.items() if x})
        rows.append(dict(engine=v["engine"], db=v["db"], pair=v["pair"], label=p["label"], family=p["family"],
                         reference_holds=holds(p["family"], p["label"], *want),
                         wrong_in="Q and Q′" if all(wrong) else "Q" if wrong[0] else "Q′" if wrong[1] else "neither",
                         reduced_sql=reduced[key][0], reduced_db=reduced[key][1]))
    distinct = Counter((r["engine"].split("-")[0], r["reduced_sql"]) for r in rows)
    summary = dict(
        pairs=len(pairs), identical_text_dropped=dropped, databases=len(dbs), depth=6, seed=11,
        engines={"duckdb": "1.1.3", "mysql-9.4.0": "9.4.0", "mysql-26.7.0": "26.7.0"},
        note="Execution counts were not saved (the original summary step crashed); violations.jsonl is complete. "
             "Triage below uses the reference evaluator (gtrans/refeval.py).",
        violations=len(viol), violating_pairs=len({r["pair"] for r in rows}),
        reference_violates=sum(not r["reference_holds"] for r in rows),
        by_engine=dict(Counter(r["engine"] for r in rows)),
        distinct_reduced_cases=[dict(system=s, reduced_sql=q, violations=n,
                                     example_db=next(r["reduced_db"] for r in rows if r["reduced_sql"] == q))
                                for (s, q), n in distinct.most_common()],
    )
    (OUT / "triage.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    print(json.dumps(summary, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main(*sys.argv[1:])
