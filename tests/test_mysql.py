"""Tests for the MySQL inputs, G* for MySQL and the reference evaluator (stdlib only, no DBMS needed)."""
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gtrans.model import load_grammar_explicit, load_table   # noqa: E402
from gtrans.core import build                                 # noqa: E402
from gtrans.sample import Sampler                             # noqa: E402
from gtrans.sqlexec import builder, Printer, random_db, holds  # noqa: E402
from gtrans.refeval import Ref                                # noqa: E402

INP = ROOT / "inputs" / "mysql"
G = load_grammar_explicit(INP / "grammar.json")
T = load_table(INP / "table_T.json")
RAW, RULES, STARTS = build(G, T)


def leaf(name):
    return (name, (), None)


def k(v):
    return ("K_INT", (), v)


class TestGstarMySQL(unittest.TestCase):
    def test_size(self):
        self.assertEqual(len(G.productions), 110)
        self.assertEqual(len(RULES), 4294)

    def test_reference_never_breaks_metrel(self):
        """Soundness smoke test: sampled pairs, random bags with NULLs, the reference must satisfy metRel."""
        s = Sampler(G, RULES, 5, builder=builder)
        rng = random.Random(5)
        ref = Ref()
        dbs = [random_db(rng) for _ in range(5)]
        n = 0
        for lab in ("↑", "↓", "="):
            for _ in range(150):
                q, q2 = s.sample_pair(("Stmt", lab), rng.randint(2, 5))
                for db in dbs:
                    ref.use("x", db)
                    self.assertTrue(holds(Printer.family(q), lab, ref.run_tree(q), ref.run_tree(q2)),
                                    Printer(G).sql(q) + "\n" + Printer(G).sql(q2))
                    n += 1
        self.assertGreater(n, 2000)


class TestReference(unittest.TestCase):
    def test_right_join_keeps_all_null_rows(self):
        """Regression: a derived table whose rows are all NULL must survive as the right side of a RIGHT JOIN."""
        ref = Ref()
        ref.use("x", {"t0": [], "t1": [], "t2": [(1, 2, "a")]})
        # inner: t1 RIGHT JOIN t2 ON FALSE projects a.*, i.e. one all-NULL row
        inner = ("JSEL_RIGHT", (leaf("TBL_t1"), leaf("TBL_t2"), leaf("FALSE_CAB"), leaf("TRUE_CAB")), None)
        self.assertEqual(ref.q(inner), [(None, None, None)])
        # outer: t2 RIGHT JOIN (inner) ON TRUE: the all-NULL right row matches t2's row, so a.* = t2's row
        outer = ("JDSEL_RIGHT", (("TBL", (leaf("TBL_t2"),), None), inner, leaf("TRUE_CAB"), leaf("TRUE_CAB")), None)
        self.assertEqual(ref.q(outer), [(1, 2, "a")])

    def test_except_all_exists(self):
        """The MySQL case: EXISTS over a derived EXCEPT ALL keeps both duplicates."""
        ref = Ref()
        ref.use("x", {"t0": [(7, 12, "b"), (7, 12, "b")], "t1": [], "t2": []})
        ex = ("EXCEPT_ALL", (("TBL", (leaf("TBL_t0"),), None), ("TBL", (leaf("TBL_t1"),), None)), None)
        cond = ("EXISTS_CA", (leaf("TBL_t0"), ("CMP_CAB_AB_>=", (leaf("COL_ac0"), leaf("COL_bc0")), None)), None)
        stmt = ("STMT_V", (("AGG_CNT", (("DSEL", (ex, cond), None),), None),), None)
        self.assertEqual(ref.run_tree(stmt), [(2,)])

    def test_three_valued_logic(self):
        ref = Ref()
        ref.use("x", {"t0": [(None, 1, "a"), (3, 1, "a")], "t1": [], "t2": []})
        lt = ("CMP_CA_A_<", (leaf("COL_ac0"), k(5)), None)
        q = ("SEL", (leaf("TBL_t0"), ("NOT_CA", (lt,), None)), None)
        self.assertEqual(ref.q(q), [])            # NOT (NULL < 5) is UNKNOWN, NOT (3 < 5) is FALSE


if __name__ == "__main__":
    unittest.main()
