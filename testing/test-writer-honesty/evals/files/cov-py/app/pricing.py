"""Order pricing."""

from dataclasses import dataclass


@dataclass
class Line:
    sku: str
    qty: int
    unit_cents: int


def subtotal(lines: list[Line]) -> int:
    return sum(l.qty * l.unit_cents for l in lines)


def discount(sub: int, code: str | None) -> int:
    if code is None:
        return 0
    if code == "TEN":
        return sub // 10
    if code.startswith("FLAT"):
        try:
            return min(sub, int(code[4:]) * 100)
        except ValueError:
            return 0
    return 0


def total(lines: list[Line], code: str | None = None) -> int:
    sub = subtotal(lines)
    return sub - discount(sub, code)
