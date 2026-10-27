"""Sample pairs from G* for MySQL and run them on MySQL servers and DuckDB; triage violations.

Usage: python scripts/run_mysql.py N_PAIRS N_DBS MAX_DEPTH SEED OUTDIR port:name [port:name ...]
"""
import json
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gtrans.model import load_grammar_explicit, load_table          # noqa: E402
from gtrans.core import build                                       # noqa: E402
from gtrans.sample import Sampler                                   # noqa: E402
from gtrans.sqlexec import builder, Printer, random_db, MySQL, DuckDB, holds, same_result   # noqa: E402
from gtrans.writer import show_pattern                              # noqa: E402
from gtrans.refeval import Ref                                      # noqa: E402

LABELS = ["↑", "↓", "="]


def load():
    inp = ROOT / "inputs" / "mysql"
    g = load_grammar_explicit(inp / "grammar.json")
    T = load_table(inp / "table_T.json")
    raw, rules, starts = build(g, T)
    return g, T, raw, rules


def weight(rule):
    # fewer constant TRUE / FALSE leaves, so that most predicates are real comparisons
    K = rule.kind
    if K.kind == "copy" and hasattr(K.q, "prod") and K.q.prod.split("_")[0] in ("TRUE", "FALSE"):
        return 0.15
    return 1.0


def edits_of(trace, g):
    return [f"{r.kind.kind}: {show_pattern(r.kind.q, g)} ⇒ {show_pattern(r.kind.q2, g)} [{r.head[0]}]"
            for _, r in trace if r.kind.kind != "copy"]


def sample_pairs(g, rules, n, depth, seed):
    s = Sampler(g, rules, seed, builder=builder, weight=weight)
    pr = Printer(g)
    rng = random.Random(seed)
    pairs, seen, dropped = [], set(), 0
    while len(pairs) < n:
        lab = LABELS[len(pairs) % 3]
        trace = []
        q, q2 = s.sample_pair(("Stmt", lab), rng.randint(2, depth), trace)
        a, b = pr.sql(q), pr.sql(q2)
        if a == b:
            dropped += 1
            continue
        if (a, b) in seen:
            continue
        seen.add((a, b))
        pairs.append(dict(id=len(pairs), family=pr.family(q), label=lab, q=a, q2=b, edits=edits_of(trace, g),
                          tree_q=q, tree_q2=q2))
    return pairs, dropped


def main(n=3000, n_dbs=8, depth=5, seed=1, outdir="outputs/mysql/run", *servers):
    n, n_dbs, depth, seed = int(n), int(n_dbs), int(depth), int(seed)
    out = ROOT / outdir
    out.mkdir(parents=True, exist_ok=True)
    g, T, raw, rules = load()
    t0 = time.time()
    pairs, dropped = sample_pairs(g, rules, n, depth, seed)
    (out / "pairs.jsonl").write_text("\n".join(json.dumps(p, ensure_ascii=False) for p in pairs) + "\n")
    rng = random.Random(seed + 100)
    dbs = [random_db(rng) for _ in range(n_dbs)]
    (out / "databases.json").write_text(json.dumps(dbs))
    engines = [DuckDB()] + [MySQL(int(s.split(":")[0]), s.split(":")[1]) for s in servers]
    results = {}                       # (engine, db, pair id) -> (ok, ra, rb) or error
    stats = defaultdict(Counter)
    for eng in engines:
        for di, db in enumerate(dbs):
            eng.use(f"gt{seed}_{di}", db)
            for p in pairs:
                try:
                    ra, rb = eng.run(p["q"]), eng.run(p["q2"])
                    ok = holds(p["family"], p["label"], ra, rb)
                    results[(eng.name, di, p["id"])] = (ok, ra, rb)
                    stats[eng.name]["ok" if ok else "violation"] += 1
                except Exception as e:  # noqa: BLE001
                    results[(eng.name, di, p["id"])] = ("error", str(e)[:300])
                    stats[eng.name]["error"] += 1
    # ---- triage: compare each violation with DuckDB's results on the same database
    viol = []
    for (en, di, pid), res in results.items():
        if res[0] is not False:
            continue
        p = pairs[pid]
        ref = results.get(("duckdb", di, pid))
        entry = dict(engine=en, db=di, pair=pid, family=p["family"], label=p["label"], q=p["q"], q2=p["q2"],
                     edits=p["edits"], result_q=repr(res[1])[:500], result_q2=repr(res[2])[:500])
        if en == "duckdb":
            entry["class"] = "reference engine violates (T entry wrong, or DuckDB bug)"
        elif ref is None or ref[0] == "error":
            entry["class"] = "no reference"
        else:
            dq = same_result(p["family"], res[1], ref[1])
            dq2 = same_result(p["family"], res[2], ref[2])
            entry["mysql_q_matches_duckdb"], entry["mysql_q2_matches_duckdb"] = dq, dq2
            if ref[0] is False:
                entry["class"] = "both engines violate (suspect T)"
            elif dq and dq2:
                entry["class"] = "same results as DuckDB, yet violation (check oracle)"
            else:
                entry["class"] = "MySQL differs from DuckDB: candidate MySQL bug in " + \
                                 ("Q" if not dq and dq2 else "Q′" if dq and not dq2 else "Q and Q′")
        viol.append(entry)
    (out / "violations.jsonl").write_text("\n".join(json.dumps(v, ensure_ascii=False, default=str) for v in viol) + ("\n" if viol else ""))
    errors = Counter()
    for (en, di, pid), res in results.items():
        if res[0] == "error":
            errors[(en, res[1][:120])] += 1
    summary = dict(pairs=len(pairs), identical_text_dropped=dropped, databases=n_dbs, depth=depth, seed=seed,
                   engines={e.name: e.version for e in engines},
                   executions={k: dict(v) for k, v in stats.items()},
                   pairs_by_family_label=dict(Counter(f"{p['family']} {p['label']}" for p in pairs)),
                   violations_by_class={f"{e} | {c}": n for (e, c), n in Counter((v["engine"], v["class"]) for v in viol).most_common()},
                   violating_pairs_by_engine={e.name: len({v["pair"] for v in viol if v["engine"] == e.name}) for e in engines},
                   top_errors=[[en, msg, c] for (en, msg), c in errors.most_common(10)],
                   seconds=round(time.time() - t0, 1))
    (out / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=str))
    print(json.dumps(summary, indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main(*sys.argv[1:])
