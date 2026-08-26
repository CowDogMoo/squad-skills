from app.pricing import Line, subtotal


def test_subtotal():
    assert subtotal([Line("a", 2, 150), Line("b", 1, 100)]) == 400
