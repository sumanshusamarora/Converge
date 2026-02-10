"""Tests for API contract diffing and CLI command behavior."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from converge.cli.main import main
from converge.contracts.api_contract import ApiContract, diff_contracts


def _write_contract(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_diff_detects_added_and_removed_endpoints() -> None:
    old = ApiContract(name="svc", version="1", endpoints={"/a": {"GET": {}}, "/b": {"GET": {}}})
    new = ApiContract(name="svc", version="2", endpoints={"/a": {"GET": {}}, "/c": {"GET": {}}})

    result = diff_contracts(old, new)

    assert result["added_endpoints"] == ["/c"]
    assert result["removed_endpoints"] == ["/b"]


def test_diff_detects_method_and_field_changes() -> None:
    old = ApiContract(
        name="svc",
        version="1",
        endpoints={
            "/users": {
                "GET": {
                    "request": {"fields": {"includeInactive": "bool"}},
                    "response": {"fields": {"id": "int", "name": "string"}},
                },
                "POST": {
                    "request": {"fields": {"name": "string"}},
                    "response": {"fields": {"id": "int"}},
                },
            }
        },
    )
    new = ApiContract(
        name="svc",
        version="2",
        endpoints={
            "/users": {
                "GET": {
                    "request": {"fields": {"includeInactive": "bool", "region": "string"}},
                    "response": {"fields": {"id": "string", "email": "string"}},
                },
                "PATCH": {
                    "request": {"fields": {"id": "string"}},
                    "response": {"fields": {"ok": "bool"}},
                },
            }
        },
    )

    result = diff_contracts(old, new)

    changed_endpoints = result["changed_endpoints"]
    assert isinstance(changed_endpoints, dict)
    changed = changed_endpoints["/users"]
    assert isinstance(changed, dict)
    assert changed["added_methods"] == ["PATCH"]
    assert changed["removed_methods"] == ["POST"]

    changed_methods = changed["changed_methods"]
    assert isinstance(changed_methods, dict)
    get_change = changed_methods["GET"]
    assert isinstance(get_change, dict)
    assert get_change["added_fields"] == ["email", "region"]
    assert get_change["removed_fields"] == ["name"]
    assert get_change["changed_fields"] == [
        {"field": "id", "from": "int", "to": "string", "where": "response"}
    ]


def test_diff_identical_contracts_is_empty() -> None:
    contract = ApiContract(
        name="svc",
        version="1",
        endpoints={"/ping": {"GET": {"response": {"fields": {"ok": "bool"}}}}},
    )

    result = diff_contracts(contract, contract)

    assert result == {
        "added_endpoints": [],
        "removed_endpoints": [],
        "changed_endpoints": {},
    }


def test_cli_contract_diff_outputs_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    old_contract = {
        "name": "svc",
        "version": "1",
        "endpoints": {"/v1": {"GET": {"response": {"fields": {"id": "int"}}}}},
    }
    new_contract = {
        "name": "svc",
        "version": "2",
        "endpoints": {"/v2": {"GET": {"response": {"fields": {"id": "int"}}}}},
    }
    old_path = tmp_path / "old.json"
    new_path = tmp_path / "new.json"
    _write_contract(old_path, old_contract)
    _write_contract(new_path, new_contract)

    exit_code = main(["contract-diff", "--old", str(old_path), "--new", str(new_path)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["added_endpoints"] == ["/v2"]
    assert payload["removed_endpoints"] == ["/v1"]


def test_cli_contract_diff_fails_on_invalid_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old_path = tmp_path / "old.json"
    new_path = tmp_path / "new.json"
    old_path.write_text("not-json", encoding="utf-8")
    _write_contract(new_path, {"name": "svc", "version": "1", "endpoints": {}})

    with pytest.raises(SystemExit) as exc:
        main(["contract-diff", "--old", str(old_path), "--new", str(new_path)])

    captured = capsys.readouterr()
    assert exc.value.code == 2
    assert "Invalid JSON" in captured.err
