from statemachine import State


def test_transition_list_or_operator():
    s1 = State("s1", initial=True)
    s2 = State("s2")
    s3 = State("s3")
    s4 = State("s4", final=True)

    t12 = s1.to(s2)
    t23 = s2.to(s3)
    t34 = s3.to(s4)

    cycle = t12 | t23 | t34

    assert [(t.source.name, t.target.name) for t in t12] == [("s1", "s2")]
    assert [(t.source.name, t.target.name) for t in t23] == [("s2", "s3")]
    assert [(t.source.name, t.target.name) for t in t34] == [("s3", "s4")]
    assert [(t.source.name, t.target.name) for t in cycle] == [
        ("s1", "s2"),
        ("s2", "s3"),
        ("s3", "s4"),
    ]
