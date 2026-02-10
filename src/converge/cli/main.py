"""Command-line interface for Converge."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from converge import __version__
from converge.contracts.api_contract import ApiContract, EndpointSpec, diff_contracts


def _load_contract(path: Path) -> ApiContract:
    try:
        with path.open("r", encoding="utf-8") as handle:
            raw_data: Any = json.load(handle)
    except OSError as exc:
        msg = f"Failed to read contract file '{path}': {exc}"
        raise ValueError(msg) from exc
    except json.JSONDecodeError as exc:
        msg = f"Invalid JSON in contract file '{path}': {exc}"
        raise ValueError(msg) from exc

    if not isinstance(raw_data, dict):
        msg = f"Contract file '{path}' must contain a JSON object."
        raise ValueError(msg)

    name = raw_data.get("name")
    version = raw_data.get("version")
    endpoints = raw_data.get("endpoints")

    if not isinstance(name, str) or not isinstance(version, str) or not isinstance(endpoints, dict):
        msg = (
            f"Contract file '{path}' must include string 'name', string 'version', "
            "and object 'endpoints'."
        )
        raise ValueError(msg)

    normalized_endpoints: dict[str, EndpointSpec] = {}
    for path_key, endpoint_spec in endpoints.items():
        if not isinstance(path_key, str) or not isinstance(endpoint_spec, dict):
            msg = f"Endpoint entries in '{path}' must be objects keyed by strings."
            raise ValueError(msg)
        normalized_endpoint: EndpointSpec = {}
        for method_name, method_spec in endpoint_spec.items():
            if not isinstance(method_name, str) or not isinstance(method_spec, dict):
                msg = f"Endpoint methods in '{path}' must be objects keyed by strings."
                raise ValueError(msg)
            normalized_endpoint[method_name] = method_spec
        normalized_endpoints[path_key] = normalized_endpoint

    return ApiContract(name=name, version=version, endpoints=normalized_endpoints)


def _run_contract_diff(old_path: Path, new_path: Path) -> int:
    old_contract = _load_contract(old_path)
    new_contract = _load_contract(new_path)
    diff = diff_contracts(old_contract, new_contract)
    print(json.dumps(diff, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build and return the top-level argument parser."""
    parser = argparse.ArgumentParser(prog="converge")
    parser.add_argument("--version", action="version", version=f"converge {__version__}")

    subparsers = parser.add_subparsers(dest="command")
    contract_diff_parser = subparsers.add_parser(
        "contract-diff", help="Diff two API contract files"
    )
    contract_diff_parser.add_argument(
        "--old", required=True, type=Path, help="Path to old contract JSON"
    )
    contract_diff_parser.add_argument(
        "--new", required=True, type=Path, help="Path to new contract JSON"
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the Converge CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "contract-diff":
        try:
            return _run_contract_diff(args.old, args.new)
        except ValueError as exc:
            parser.error(str(exc))

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
