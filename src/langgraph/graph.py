"""Minimal subset of langgraph.graph used by this project."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

END = "__END__"


@dataclass
class _CompiledGraph:
    entry_point: str
    nodes: dict[str, Callable[[Any], Any]]
    edges: dict[str, str]

    def invoke(self, state: Any) -> Any:
        node_name = self.entry_point
        current_state = state
        while node_name != END:
            node = self.nodes[node_name]
            current_state = node(current_state)
            node_name = self.edges[node_name]
        return current_state


class StateGraph:
    """Small state graph executor for deterministic linear workflows."""

    def __init__(self, _state_type: Any) -> None:
        self._nodes: dict[str, Callable[[Any], Any]] = {}
        self._edges: dict[str, str] = {}
        self._entry_point: str | None = None

    def add_node(self, name: str, node: Callable[[Any], Any]) -> None:
        self._nodes[name] = node

    def set_entry_point(self, name: str) -> None:
        self._entry_point = name

    def add_edge(self, src: str, dst: str) -> None:
        self._edges[src] = dst

    def compile(self) -> _CompiledGraph:
        if self._entry_point is None:
            raise ValueError("Entry point not set")
        return _CompiledGraph(entry_point=self._entry_point, nodes=self._nodes, edges=self._edges)
