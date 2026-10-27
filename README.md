# GTrans: from a grammar G and an operator table T to a test grammar G*

This repository implements the algorithm of the note "Composing Q, Q′ and metRel(Q, Q′) from a grammar G and an operator table T" for the toy language TinyQ and for MySQL (a core of ValScope's grammar; see the MySQL section at the end). GTrans reads G and T and writes G*, a grammar whose every derivation prints a gold query Q, a mutant query Q′ and their metamorphic relation metRel(Q, Q′) ∈ {⊆, ⊇, =}.

## Layout

```
inputs/tinyq/
  grammar.json     G as a template: the operators W, op², op¹*, op²* and how atoms are formed
  schema.json      database schema: tables, columns, types and constant domains (atoms come from here)
  table_T.json     T: signs (α, β, γ), identity (greatest / least per slot), order codes Ci.j, laws L1..L10
gtrans/
  labels.py        labels {id, =, ↑, ↓}, Table 1 (sign action ⊗) and Table 2 (composition ∘)
  model.py         loads G (template + schema) and T; order relation from the Ci.j codes
  kinds.py         node kinds of Table 3: copy, swap, insert, drop, constant, law
  core.py          GTrans: one rule per node kind and child-label choice with ℓ ≠ ?; grammar reduction
  sample.py        sampling from G (fresh subtrees) and from G* (pairs)
  semantics.py     TinyQ reference evaluator, TinyQ and SQL printers, SQLite runner
  writer.py        writes G* as text and JSON
scripts/
  build_gstar.py     build G* and write outputs/<lang>/
  check_gstar.py     sample pairs, run them on random databases (reference evaluator and SQLite), check metRel
  sample_examples.py print sampled triples with their derivations, on the People table of Figure 1
tests/test_gtrans.py unit tests (tables, known rules, counts, and a deliberately wrong T that must be caught)
outputs/tinyq/
  Gstar.txt          the full G*, grouped by labelled non-terminal and node kind
  Gstar.json         the same rules, machine-readable
  Gstar_summary.md   counts per kind, before and after reduction; G as built from the schema
  samples.txt        sampled triples with derivations
  check_report.txt   result of check_gstar.py
```

## Run

```
conda env create -f environment.yml        # or: conda create --name gtrans --file environment.lock.txt
conda activate gtrans
python scripts/build_gstar.py tinyq        # writes outputs/tinyq/Gstar.txt, .json, _summary.md
python scripts/check_gstar.py 3000 60 5 1  # pairs per start symbol, databases, depth budget, seed
python scripts/sample_examples.py 4 4 11
python -m unittest discover -s tests -v
```

Only the Python standard library is used (sqlite3 included); the environment pins Python 3.11.

## Reading Gstar.txt

`X[ℓ]` is the labelled non-terminal X_ℓ. A rule is printed as

```
Query[↑] → x1 EXCEPT x2  ⇒  x1 UNION x2
    where x1: Query[id], x2: Query[↑]
    ℓ = ↑ ∘ (+⊗id) ∘ (+⊗↑) = ↑        [order: EXCEPT ≼ UNION]
```

The left of ⇒ is what the rule adds to Q, the right what it adds to Q′; x1, x2 are shared children, derived further from the labelled non-terminals given after `where`; a fresh subtree z (insert, drop) is sampled from G on one side only. The last line is rule (★) of the note: the own change r composed with each shared child's label passed through the sign of its slot on the Q′ side. A copy rule shows its right-hand side once.

## Using another language

Write `grammar.json` (operators and their slots), `schema.json` (tables or node labels, columns or properties, types and domains) and `table_T.json` (signs, identities, order codes, laws) for the language, then run `build_gstar.py <lang>`. To run the semantic check, add an evaluator for the language in `semantics.py`.

## Assumptions (as in the note)

Set semantics, two-valued logic (no NULLs), deterministic operators, and no context (named subqueries, aliases). Laws must be linear: every variable occurs once on each side. TinyQ has one base table, so every query returns rows of People and UNION / EXCEPT are always well typed.

## MySQL (G from ValScope's grammar, T for MySQL)

```
inputs/mysql/
  make_inputs.py     writes grammar.json (G, 110 productions) and table_T.json (T); README_mysql.md maps ValScope's BNF to G
gtrans/
  sqlexec.py         tree builder, SQL printer, random bags with NULLs, MySQL and DuckDB runners, the metRel check
  refeval.py         reference evaluator for MySQL G trees (bags, NULLs, 3VL), the oracle for triage
scripts/
  build_gstar.py mysql   writes outputs/mysql/Gstar.txt, Gstar.json, Gstar_summary.md
  measure_gain.py        M1 edit inventory, M2 pair-shape coverage (exact and sampled), M3 out of reach
  mirror_check.py        M2 again with mirror images merged
  run_mysql.py           run A (pairs on MySQL and DuckDB, DuckDB used for triage)
  triage_runA.py         run A judged again with the reference evaluator, reduced cases
  hunt.py                runs B and C: sample arms (G*, G*_V, G*_P), exec per engine, triage and reduction
  hunt_exec_all.sh       one exec process per engine
  reduce_case.py         greedy reducer of a failing statement and its database
tests/test_mysql.py      G* size, reference never breaks metRel on sampled pairs, reference regression tests
envs/                    gtrans-mysql (run A, DuckDB 1.1.3) and gtrans-hunt (runs B and C, DuckDB 2.0.0): yml, conda lock, pip freeze
docs/                    RESULTS.md, EXPERIMENT_PLAN.md, BUG_mysql_except_all_weedout.md
outputs/mysql/           G*, measures/, runA/, runB/, runC/ (pairs with trees, databases, per-engine results, summaries)
```

MySQL servers are the official Docker images, for example `docker run -d --name m97 -e MYSQL_ROOT_PASSWORD=gt -p 32772:3306 mysql:9.7.2`.

```
python scripts/build_gstar.py mysql
python scripts/measure_gain.py 20000 5 7 outputs/mysql/measures
python scripts/hunt.py sample 10000 10 6 23 outputs/mysql/runB
scripts/hunt_exec_all.sh outputs/mysql/runB $(which python)      # edit the ports inside first
python scripts/hunt.py triage outputs/mysql/runB 32772:mysql-9.7.2
```
