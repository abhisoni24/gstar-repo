"""Unit tests: the two tables, a few rules of G* for TinyQ, the counts, and a deliberately wrong table."""
import copy
import itertools
import json
import random
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gtrans.labels import LABELS, TOP, ID, EQ, UP, DN, act, compose, flip   # noqa: E402
from gtrans.model import load_grammar, load_table, Table                   # noqa: E402
from gtrans.core import build                                               # noqa: E402
from gtrans.sample import Sampler                                           # noqa: E402
from gtrans.semantics import random_db, column_index, eval_query            # noqa: E402

INP = ROOT / "inputs" / "tinyq"
G = load_grammar(INP / "grammar.json", INP / "schema.json")
T = load_table(INP / "table_T.json")
RAW, RULES, STARTS = build(G, T)


def rules_for(head, kind, q_contains=""):
    from gtrans.writer import rule_text
    return [r for r in RULES if r.head == head and r.kind.kind == kind and q_contains in rule_text(r, G)[1]]


class TestTables(unittest.TestCase):
    def test_table1(self):
        self.assertEqual([act("+", l) for l in LABELS], [ID, EQ, UP, DN])
        self.assertEqual([act("-", l) for l in LABELS], [ID, EQ, DN, UP])
        self.assertEqual([act("=", l) for l in LABELS], [ID, EQ, EQ, EQ])
        self.assertEqual([act("0", l) for l in LABELS], [ID, EQ, TOP, TOP])
        self.assertEqual(act("=", TOP), EQ)

    def test_table2(self):
        L5 = LABELS + (TOP,)
        for a, b, c in itertools.product(L5, repeat=3):
            self.assertEqual(compose(a, b), compose(b, a))
            self.assertEqual(compose(compose(a, b), c), compose(a, compose(b, c)))
        self.assertEqual(compose(UP, DN), TOP)
        self.assertEqual(compose(EQ, UP), UP)


class TestGstar(unittest.TestCase):
    def test_counts(self):
        c = Counter(r.kind.kind for r in RULES)
        self.assertEqual(dict(c), {"copy": 99, "swap": 56, "insert": 24, "drop": 24, "constant": 2, "law": 786})
        self.assertEqual(len(RULES), 991)

    def test_no_question_mark_and_productive(self):
        heads = {r.head for r in RULES}
        for r in RULES:
            self.assertNotEqual(r.head[1], TOP)
            for ch in r.children:
                self.assertIn(ch, heads)

    def test_except_copy_up_has_five_rules(self):
        rs = rules_for((G.start, UP), "copy", "EXCEPT")
        self.assertEqual(sorted(r.labels for r in rs),
                         sorted([(UP, ID), (UP, EQ), (UP, DN), (ID, DN), (EQ, DN)]))

    def test_known_rules(self):
        self.assertTrue(rules_for((G.pred_sort, DN), "swap", "OR"))               # OR ⇒ AND is ↓
        self.assertTrue(rules_for((G.pred_sort, UP), "swap", "AND"))              # AND ⇒ OR is ↑
        self.assertTrue(rules_for((G.start, DN), "insert"))                       # x ⇒ x WHERE c, x ⇒ x EXCEPT z
        self.assertTrue(rules_for(("Const.age", UP), "constant"))
        self.assertFalse([r for r in RULES if r.head[0] == "Const.city" and r.head[1] != ID])
        self.assertTrue(rules_for((G.pred_sort, EQ), "law", "NOT (a > k)"))      # L10


class TestNoteExamples(unittest.TestCase):
    """The rules used by examples A to F of the note exist in G* with these child labels."""
    def has(self, head, kind, body, labels):
        from gtrans.writer import rule_text
        hits = [r for r in RULES if r.head == head and r.kind.kind == kind
                and rule_text(r, G)[1] == body and r.labels == labels]
        self.assertTrue(hits, (head, kind, body, labels))

    def test_examples(self):
        Q, C = G.start, G.pred_sort
        self.has((C, DN), "copy", "x1 > x2", (ID, UP))                                     # A, C
        self.has(("Const.age", UP), "constant", "k  ⇒  k′   with k′ > k", ())               # A, C
        self.has((Q, UP), "copy", "x1 EXCEPT x2", (UP, DN))                                 # B
        self.has((Q, UP), "drop", "x1 WHERE z  ⇒  x1", (ID,))                               # B
        self.has((Q, DN), "insert", "x1  ⇒  x1 WHERE z", (ID,))                             # B
        self.has((C, DN), "swap", "x1 OR x2  ⇒  x1 AND x2", (DN, ID))                       # C
        self.has((Q, EQ), "law", "x UNION y  ⇒  y UNION x", (EQ, ID))                       # D
        self.has((C, EQ), "law", "x  ⇒  NOT (NOT x)", (ID,))                                # D
        self.has((C, DN), "insert", "x1  ⇒  x1 AND z", (ID,))                               # E
        self.has((C, DN), "law", "NOT (x AND y)  ⇒  (NOT x) OR (NOT y)", (UP, ID))          # F
        self.has((C, UP), "copy", "x1 > x2", (ID, DN))                                     # F


class TestWrongTable(unittest.TestCase):
    def test_wrong_sign_is_caught(self):
        """If T wrongly says EXCEPT is monotone in its right slot, sampled pairs must break."""
        ops = copy.deepcopy(T.ops)
        ops["EXCEPT"]["signs"] = ["+", "+"]
        bad = Table(ops, T.laws)
        _, rules, _ = build(G, bad)
        s = Sampler(G, rules, seed=3)
        schema = json.loads((INP / "schema.json").read_text())
        rng = random.Random(4)
        dbs = [random_db(schema, rng) for _ in range(30)]
        cols = column_index(schema)
        broken = 0
        for _ in range(400):
            q, q2 = s.sample_pair((G.start, UP), 3)
            if any(not eval_query(q, d, cols) <= eval_query(q2, d, cols) for d in dbs):
                broken += 1
        self.assertGreater(broken, 0)


if __name__ == "__main__":
    unittest.main()
