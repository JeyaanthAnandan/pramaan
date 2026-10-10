"""Calculation tree: every derived number keeps its formula and its inputs.

Leaves reference evidence records, refdata entries or explicit assumptions. The Evidence
Lens in the UI walks this tree, so a judge or verifier can click from a buyer cost down
to the highlighted region of a gas invoice.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

D = Decimal

# Data-status vocabulary (brief section 5.4)
VERIFIED_2R = "VERIFIED_2R"
APPROVED = "APPROVED"
NEEDS_REVIEW = "NEEDS_REVIEW"
MISSING = "MISSING"
DEFAULT_USED = "DEFAULT_USED"
ASSUMPTION = "ASSUMPTION"
REFDATA = "REFDATA"
CALCULATED = "CALCULATED"
INPUT = "INPUT"

GOOD_STATUSES = {VERIFIED_2R, APPROVED}


def q(value: Decimal | None, places: int = 3) -> str | None:
    """Display rounding (EC tables round to 3 decimals). Never used inside calculations."""
    if value is None:
        return None
    return str(value.quantize(D(1).scaleb(-places), rounding=ROUND_HALF_UP))


@dataclass
class Node:
    id: str
    label: str
    value: Decimal | None
    unit: str
    formula: str | None = None
    children: list[str] = field(default_factory=list)
    source: dict[str, Any] | None = None
    status: str = CALCULATED
    note: str | None = None

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        d["value"] = None if self.value is None else str(self.value)
        d["display"] = q(self.value, DISPLAY_PLACES.get(self.unit, 3))
        return d


DISPLAY_PLACES = {
    "EUR": 0,
    "INR": 0,
    "EUR/t": 2,
    "INR/t": 0,
    "EUR/certificate": 2,
    "INR/EUR": 4,
    "t": 1,
    "t CO2": 1,
    "certificates": 1,
    "%": 1,
    "GJ": 1,
    "MMBtu": 3,
    "SCM": 0,
}


class Tree:
    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}

    def _put(self, node: Node) -> Node:
        if node.id in self.nodes:
            raise ValueError(f"duplicate calc node id {node.id}")
        self.nodes[node.id] = node
        return node

    def leaf(
        self, id: str, label: str, value: Decimal | None, unit: str, *, source: dict[str, Any], status: str, note: str | None = None
    ) -> Node:
        return self._put(Node(id, label, value, unit, None, [], source, status, note))

    def calc(
        self,
        id: str,
        label: str,
        value: Decimal | None,
        unit: str,
        formula: str,
        children: list[str],
        note: str | None = None,
        status: str = CALCULATED,
    ) -> Node:
        for c in children:
            if c not in self.nodes:
                raise ValueError(f"{id}: unknown child {c}")
        return self._put(Node(id, label, value, unit, formula, list(children), None, status, note))

    def get(self, id: str) -> Node:
        return self.nodes[id]

    def leaves_under(self, id: str) -> list[Node]:
        out: list[Node] = []
        seen: set[str] = set()

        def walk(nid: str) -> None:
            if nid in seen:
                return
            seen.add(nid)
            n = self.nodes[nid]
            if not n.children:
                out.append(n)
            for c in n.children:
                walk(c)

        walk(id)
        return out

    def to_json(self) -> dict[str, Any]:
        return {k: v.to_json() for k, v in self.nodes.items()}
