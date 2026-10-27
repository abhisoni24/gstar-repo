"""Render inputs/<lang>/table_T.json as markdown in the note's layout (signs, identity, bound, order, laws)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SL = ["α", "β", "γ", "δ"]


def main(lang="mysql"):
    t = json.loads((ROOT / "inputs" / lang / "table_T.json").read_text())
    ops, laws = t["operators"], t["laws"]
    lids = [l["id"] for l in laws]
    lines = [f"# Table T for {lang}", "", t.get("_comment", ""), "",
             "| operator | signs (" + ", ".join(SL) + ") | identity: greatest | identity: least | bound | order | " + " | ".join(lids) + " |",
             "|---|---|---|---|---|---|" + "---|" * len(lids)]
    for op, r in ops.items():
        sg = ", ".join(r.get("signs", [])) or "(leaf)"
        idg = ", ".join(f"{SL[['alpha','beta','gamma'].index(k)]}: {v}" for k, v in r.get("identity", {}).get("greatest", {}).items())
        idl = ", ".join(f"{SL[['alpha','beta','gamma'].index(k)]}: {v}" for k, v in r.get("identity", {}).get("least", {}).items())
        bd = ", ".join(f"{SL[['alpha','beta','gamma'].index(k)]}: {v}" for k, v in r.get("bound", {}).items())
        od = ", ".join(r.get("order", []))
        ticks = " | ".join("✓" if l in r.get("laws", []) else "" for l in lids)
        lines.append(f"| {op} | {sg} | {idg} | {idl} | {bd} | {od} | {ticks} |")
    lines += ["", "## Laws", "", "| id | name | instances | first instance |", "|---|---|---|---|"]
    for l in laws:
        inst = l.get("instances_from") or l.get("instances") or []
        first = f"{json.dumps(inst[0]['lhs'])} = {json.dumps(inst[0]['rhs'])}" if inst else ""
        lines.append(f"| {l['id']} | {l['name']} | {len(inst)} | `{first}` |")
    if t.get("extremes"):
        lines += ["", "## Sort extremes", ""] + [f"- {s}: greatest {e['greatest']}, least {e['least']}" for s, e in t["extremes"].items()]
    (ROOT / "inputs" / lang / "table_T.md").write_text("\n".join(lines) + "\n")
    print(f"wrote inputs/{lang}/table_T.md")


if __name__ == "__main__":
    main(*sys.argv[1:])
