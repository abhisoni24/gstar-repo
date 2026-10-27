"""Bug hunt on MySQL with pairs from G* and from two inventory-restricted grammars (same generator, same oracle).

Arms (equal budgets, same databases):
  G*    the full G* for MySQL
  G*_V  G* restricted to ValScope's inventory: one edit per pair, at a place its mutators touch, no laws or =,
        and only constructs in ValScope's grammar (no INTERSECT ALL / EXCEPT ALL)
  G*_P  G* restricted to Pinolo's inventory: its mutators only, none inside another, no laws or =, row queries
        only, and only constructs in Pinolo's grammar
These arms are ablations of the MR inventory inside one framework, not runs of the original tools.

Every statement is also evaluated by the reference evaluator (gtrans.refeval), which is the oracle for triage:
  - reference violates metRel(Q, Q′)          -> T (or the reference) is wrong: a soundness failure
  - engine violates, engine ≠ reference      -> wrong result in the engine (candidate bug), caught by the MR
  - engine holds,   engine ≠ reference      -> wrong result in the engine that the MR did not catch
Steps:
  python scripts/hunt.py sample N_PER_ARM N_DBS MAX_DEPTH SEED OUTDIR [ARMS, e.g. G*,G*_V,G*_P]
  python scripts/hunt.py exec OUTDIR ENGINE        (ENGINE = duckdb | mysql:PORT:NAME), one process per engine
  python scripts/hunt.py triage OUTDIR port:name,port:name   (servers used to reduce failing statements)
"""
import hashlib
import json
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from gtrans.sqlexec import builder, Printer, random_db, MySQL, DuckDB, holds, same_result   # noqa: E402
from gtrans.refeval import Ref                                                              # noqa: E402

ARMS = ("G*", "G*_V", "G*_P")


def _jsonable(t):
    return [t[0], [_jsonable(k) for k in t[1]], t[2]]


def _tuple(t):
    return (t[0], tuple(_tuple(k) for k in t[1]), t[2])


# ---------------------------------------------------------------- step 1: sample the three arms
def do_sample(n, n_dbs, depth, seed, outdir, which="G*,G*_V,G*_P"):
    import measure_gain as M                 # builds G* for MySQL and the restricted grammars
    from run_mysql import edits_of, weight
    from gtrans.sample import Sampler
    n, n_dbs, depth, seed = int(n), int(n_dbs), int(depth), int(seed)
    out = ROOT / outdir
    out.mkdir(parents=True, exist_ok=True)
    pr = Printer(M.G)
    vs_place = lambda ds: all(M.valscope_mutator(d["info"], d["place"]) for d in ds)
    pn_place = lambda ds: all(M.pinolo_mutator(d["info"], d["place"]) for d in ds)
    arms = {
        "G*": (M.RULES, lambda fam, lab, ds, prods: True),
        "G*_V": (M.restricted("valscope"),
                 lambda fam, lab, ds, prods: len(ds) == 1 and vs_place(ds)
                 and not any(p.startswith(M.NOT_IN_VALSCOPE_GRAMMAR) for p in prods)),
        "G*_P": (M.restricted("pinolo"),
                 lambda fam, lab, ds, prods: len(ds) >= 1 and pn_place(ds) and fam == "rows"
                 and not any(p.startswith(M.NOT_IN_PINOLO_GRAMMAR) for p in prods)),
    }
    info = {}
    for ai, (arm, (rules, accept)) in enumerate(arms.items()):
        if arm not in which.split(","):
            continue
        s = Sampler(M.G, rules, seed + ai, builder=builder, weight=weight)
        rng = random.Random(seed + ai)
        heads = sorted({r.head for r in rules if r.head[0] == "Stmt" and r.head[1] != "id"}, key=str)
        pairs, seen, tries, rejected = [], set(), 0, Counter()
        while len(pairs) < n and tries < 200 * n:
            tries += 1
            head = heads[len(pairs) % len(heads)]
            trace = []
            q, q2 = s.sample_pair(head, rng.randint(2, depth), trace)
            a, b = pr.sql(q), pr.sql(q2)
            if a == b:
                rejected["identical text"] += 1
                continue
            fam, lab, ds = M.describe(trace)
            if not accept(fam, lab, ds, M.productions_used(q, q2)):
                rejected["outside the arm"] += 1
                continue
            if (a, b) in seen:
                rejected["duplicate"] += 1
                continue
            seen.add((a, b))
            pairs.append(dict(arm=arm, id=len(pairs), family=pr.family(q), label=head[1], q=a, q2=b,
                              edits=edits_of(trace, M.G), n_edits=len(ds),
                              tree_q=_jsonable(q), tree_q2=_jsonable(q2)))
        (out / f"pairs_{arm.replace('*', 'star')}.jsonl").write_text(
            "\n".join(json.dumps(p, ensure_ascii=False) for p in pairs) + "\n")
        info[arm] = dict(pairs=len(pairs), grammar_rules=len(rules), tries=tries, rejected=dict(rejected),
                         by_family_label=dict(Counter(f"{p['family']} {p['label']}" for p in pairs)))
        print(arm, info[arm], flush=True)
    rng = random.Random(seed + 100)
    dbs = [random_db(rng) for _ in range(n_dbs)]
    (out / "databases.json").write_text(json.dumps(dbs))
    (out / "sample_info.json").write_text(json.dumps(dict(n_per_arm=n, n_dbs=n_dbs, depth=depth, seed=seed, arms=info),
                                                      indent=1, ensure_ascii=False))


def load_pairs(out):
    pairs = {}
    for arm in ARMS:
        f = out / f"pairs_{arm.replace('*', 'star')}.jsonl"
        if f.exists():
            pairs[arm] = [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
    return pairs


def digest(family, rows):
    """Order-insensitive fingerprint of a result, for comparing engines without storing every result."""
    from gtrans.sqlexec import norm_rows
    if family == "value":
        v = rows[0][0]
        v = None if v is None else str(round(float(v), 3))
        return v
    c = norm_rows(rows)
    items = sorted((repr(tuple(float(x) if hasattr(x, "as_tuple") else x for x in k)), n) for k, n in c.items())
    return hashlib.md5(repr(items).encode()).hexdigest()[:12]


# ---------------------------------------------------------------- step 2: run one engine on every arm
def do_exec(outdir, spec):
    out = ROOT / outdir
    pairs, dbs = load_pairs(out), json.loads((out / "databases.json").read_text())
    if spec == "duckdb":
        eng = DuckDB()
    else:
        _, port, name = spec.split(":")
        eng = MySQL(int(port), name)
    ref = Ref()
    t0 = time.time()
    stats = defaultdict(Counter)
    records = []
    for di, db in enumerate(dbs):
        eng.use(f"hunt_{di}", db)
        ref.use("ref", db)
        for arm in pairs:
            for p in pairs[arm]:
                fam = p["family"]
                want = (ref.run_tree(p["tree_q"]), ref.run_tree(p["tree_q2"]))
                ref_ok = holds(fam, p["label"], *want)
                try:
                    got = (eng.run(p["q"]), eng.run(p["q2"]))
                except Exception as e:  # noqa: BLE001
                    stats[arm]["error"] += 1
                    records.append(dict(arm=arm, db=di, pair=p["id"], kind="error", msg=str(e)[:200]))
                    continue
                ok = holds(fam, p["label"], *got)
                wrong = (not same_result(fam, got[0], want[0]), not same_result(fam, got[1], want[1]))
                stats[arm]["executed"] += 1
                stats[arm]["reference violates (T unsound)"] += (not ref_ok)
                if not ok:
                    stats[arm]["engine violates"] += 1
                if any(wrong):
                    stats[arm]["engine ≠ reference, caught by MR" if not ok else "engine ≠ reference, MR silent"] += 1
                if not ok or any(wrong) or not ref_ok:
                    records.append(dict(arm=arm, db=di, pair=p["id"], kind="flag", engine_holds=ok, ref_holds=ref_ok,
                                        wrong_q=wrong[0], wrong_q2=wrong[1],
                                        got=[repr(g)[:300] for g in got], want=[repr(w)[:300] for w in want]))
    res = dict(engine=eng.name, version=eng.version, seconds=round(time.time() - t0, 1),
               stats={a: dict(c) for a, c in stats.items()}, records=records)
    (out / f"exec_{eng.name}.json").write_text(json.dumps(res, ensure_ascii=False, default=str))
    print(eng.name, eng.version, res["seconds"], json.dumps(res["stats"], ensure_ascii=False))


# ---------------------------------------------------------------- step 3: triage and reduce
def do_triage(outdir, reduce_ports=""):
    from gtrans.model import load_grammar_explicit
    from reduce_case import Case
    out = ROOT / outdir
    pairs, dbs = load_pairs(out), json.loads((out / "databases.json").read_text())
    g = load_grammar_explicit(ROOT / "inputs" / "mysql" / "grammar.json")
    pr = Printer(g)
    execs = [json.loads(f.read_text()) for f in sorted(out.glob("exec_*.json"))]
    summary = dict(engines={e["engine"]: e["version"] for e in execs},
                   stats={e["engine"]: e["stats"] for e in execs}, arms={})
    findings = []
    cache = {}
    for e in execs:
        eng = None
        for r in e["records"]:
            if r["kind"] != "flag" or (r["engine_holds"] and not (r["wrong_q"] or r["wrong_q2"]) and r["ref_holds"]):
                continue
            p = pairs[r["arm"]][r["pair"]]
            side = "tree_q2" if r["wrong_q2"] and not r["wrong_q"] else "tree_q"
            key = (e["engine"].split("-")[0], p["q"] if side == "tree_q" else p["q2"])
            entry = dict(engine=e["engine"], version=e["version"], arm=r["arm"], pair=r["pair"], db=r["db"],
                         family=p["family"], label=p["label"], edits=p["edits"], q=p["q"], q2=p["q2"],
                         got=r["got"], want=r["want"], ref_holds=r["ref_holds"],
                         wrong_in=("Q and Q′" if r["wrong_q"] and r["wrong_q2"] else "Q" if r["wrong_q"] else
                                   "Q′" if r["wrong_q2"] else "neither"))
            if not r["ref_holds"]:
                entry["class"] = "soundness failure: the reference violates metRel"
            elif entry["wrong_in"] == "neither":
                entry["class"] = "oracle problem: engine equals reference yet violates"
            else:
                entry["class"] = ("wrong result in the engine, caught by the MR" if not r["engine_holds"]
                                  else "wrong result in the engine, MR silent (both sides wrong alike)")
                if key not in cache:
                    if eng is None:
                        eng = DuckDB() if e["engine"] == "duckdb" else MySQL(
                            int(dict(x.split(":")[::-1] for x in reduce_ports.split(",") if x)[e["engine"]]), e["engine"])
                    db = {k: [tuple(x) for x in v] for k, v in dbs[r["db"]].items()}
                    c = Case(g, eng, Printer.family)
                    try:
                        t, d = c.reduce(_tuple(p[side]), db)
                        cache[key] = dict(sql=pr.sql(t), db={k: v for k, v in d.items() if v})
                    except AssertionError:
                        cache[key] = dict(sql=None, db=None)
                entry["reduced"] = cache[key]
            findings.append(entry)
    (out / "findings.jsonl").write_text("\n".join(json.dumps(f, ensure_ascii=False, default=str) for f in findings) + "\n")
    # distinct wrong-result cases by reduced statement
    distinct = defaultdict(lambda: dict(arms=Counter(), pairs=set(), engines=set()))
    for f in findings:
        if f["class"].startswith("wrong result") and f["reduced"]["sql"]:
            k = (f["engine"].split("-")[0], f["reduced"]["sql"])
            distinct[k]["arms"][f["arm"]] += 1
            distinct[k]["pairs"].add((f["arm"], f["pair"]))
            distinct[k]["engines"].add(f["engine"])
            distinct[k]["example"] = dict(engine=f["engine"], db=f["reduced"]["db"], edits=f["edits"], label=f["label"])
    summary["distinct_reduced_cases"] = [
        dict(system=k[0], reduced_sql=k[1], engines=sorted(v["engines"]), flagged_executions_by_arm=dict(v["arms"]),
             distinct_pairs_by_arm=dict(Counter(a for a, _ in v["pairs"])), example=v["example"])
        for k, v in distinct.items()]
    summary["violating_pairs_by_engine_and_arm"] = {
        e["engine"]: dict(Counter(a for a, _ in {(r["arm"], r["pair"]) for r in e["records"]
                                                  if r["kind"] == "flag" and not r["engine_holds"]}))
        for e in execs}
    summary["classes"] = dict(Counter(f"{f['engine']} | {f['arm']} | {f['class']}" for f in findings))
    (out / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=str))
    print(json.dumps(summary, indent=1, ensure_ascii=False, default=str)[:8000])


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    {"sample": do_sample, "exec": do_exec, "triage": do_triage}[cmd](*args)
