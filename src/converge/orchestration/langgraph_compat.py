"""Fallback subset of LangGraph APIs for local tests and offline environments."""

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
    conditional_edges: dict[str, Callable[[Any], str]]

    def invoke(self, state: Any) -> Any:
        node_name = self.entry_point
        current_state = state

        while node_name != END:
            node = self.nodes[node_name]
            current_state = node(current_state)
            if node_name in self.conditional_edges:
                node_name = self.conditional_edges[node_name](current_state)
            else:
                node_name = self.edges[node_name]
        return current_state


class StateGraph:
    """Minimal state graph executor with conditional edge support."""

    def __init__(self, _state_type: Any) -> None:
        self._nodes: dict[str, Callable[[Any], Any]] = {}
        self._edges: dict[str, str] = {}
        self._conditional_edges: dict[str, Callable[[Any], str]] = {}
        self._entry_point: str | None = None

    def add_node(self, name: str, node: Callable[[Any], Any]) -> None:
        self._nodes[name] = node

    def set_entry_point(self, name: str) -> None:
        self._entry_point = name

    def add_edge(self, src: str, dst: str) -> None:
        self._edges[src] = dst

    def add_conditional_edges(self, src: str, route_fn: Callable[[Any], str]) -> None:
        self._conditional_edges[src] = route_fn

    def compile(self) -> _CompiledGraph:
        if self._entry_point is None:
            raise ValueError("Entry point not set")
        return _CompiledGraph(
            entry_point=self._entry_point,
            nodes=self._nodes,
            edges=self._edges,
            conditional_edges=self._conditional_edges,
        )


def interrupt(payload: dict[str, Any]) -> dict[str, Any]:
    """Fallback interrupt hook for environments without real LangGraph runtime."""
    return {"human_decision": {"action": "defer", "context": payload.get("goal", "")}}
