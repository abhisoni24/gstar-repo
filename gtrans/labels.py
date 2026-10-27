"""Labels and the two fixed tables of the note.

Labels L = {id, =, ↑, ↓} describe a pair (x, x′); "?" means no guaranteed relation.
Table 1 (sign action ⊗) and Table 2 (composition ∘) are the same for every language.
"""

ID, EQ, UP, DN, TOP = "id", "=", "↑", "↓", "?"
LABELS = (ID, EQ, UP, DN)
SIGNS = ("+", "-", "=", "0")


def act(sign, label):
    """Table 1: label of an operator's output when the input in a slot with `sign` changes with `label`."""
    if sign not in SIGNS:
        raise ValueError(f"unknown sign {sign!r}")
    if label == ID:
        return ID
    if sign == "=":
        return EQ                      # a slot with no effect: the output stays equal
    if label == TOP:
        return TOP
    if label == EQ:
        return EQ                      # same input result, same output (deterministic operators)
    if sign == "+":
        return label
    if sign == "-":
        return flip(label)
    return TOP                         # sign 0 with ↑ or ↓


def flip(label):
    """flip(ℓ) = − ⊗ ℓ: swaps ↑ and ↓, keeps id, = and ?."""
    return {UP: DN, DN: UP}.get(label, label)


def compose(a, b):
    """Table 2: label of two changes made one after the other (commutative, associative)."""
    if TOP in (a, b):
        return TOP
    if a == ID:
        return b
    if b == ID:
        return a
    if a == EQ:
        return b
    if b == EQ:
        return a
    return a if a == b else TOP


def compose_all(labels):
    out = ID
    for x in labels:
        out = compose(out, x)
    return out


def act_path(path_signs, label):
    """Apply the signs on a path from a node down to one of its children (outermost first)."""
    out = label
    for s in reversed(path_signs):
        out = act(s, out)
    return out


def sign_product(path_signs):
    """Composite sign of a path, for display: the sign σ′ with σ′ ⊗ ℓ = act_path(path, ℓ) for every ℓ."""
    out = "+"
    for s in path_signs:
        if out == "=" or s == "=":
            out = "="
        elif out == "0" or s == "0":
            out = "0"
        else:
            out = "+" if out == s else "-"
    return out
