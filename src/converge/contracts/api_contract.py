"""API contract model and diff utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MethodSpec = dict[str, Any]
EndpointSpec = dict[str, MethodSpec]


@dataclass(frozen=True)
class ApiContract:
    """Represents a versioned API contract."""

    name: str
    version: str
    endpoints: dict[str, EndpointSpec]


def _extract_fields(method_spec: MethodSpec, location: str) -> dict[str, str]:
    section = method_spec.get(location)
    if not isinstance(section, dict):
        return {}
    fields = section.get("fields")
    if not isinstance(fields, dict):
        return {}
    return {str(field_name): str(field_type) for field_name, field_type in fields.items()}


def _diff_method_fields(
    old_method: MethodSpec, new_method: MethodSpec
) -> dict[str, list[dict[str, str]] | list[str]]:
    added_fields: set[str] = set()
    removed_fields: set[str] = set()
    changed_fields: list[dict[str, str]] = []

    for location in ("request", "response"):
        old_fields = _extract_fields(old_method, location)
        new_fields = _extract_fields(new_method, location)

        old_names = set(old_fields)
        new_names = set(new_fields)

        added_fields.update(new_names - old_names)
        removed_fields.update(old_names - new_names)

        for field_name in old_names & new_names:
            old_type = old_fields[field_name]
            new_type = new_fields[field_name]
            if old_type != new_type:
                changed_fields.append(
                    {
                        "field": field_name,
                        "from": old_type,
                        "to": new_type,
                        "where": location,
                    }
                )

    return {
        "added_fields": sorted(added_fields),
        "removed_fields": sorted(removed_fields),
        "changed_fields": sorted(changed_fields, key=lambda item: (item["where"], item["field"])),
    }


def _diff_endpoint_methods(
    old_endpoint: EndpointSpec, new_endpoint: EndpointSpec
) -> dict[str, object]:
    old_methods = {str(method): spec for method, spec in old_endpoint.items()}
    new_methods = {str(method): spec for method, spec in new_endpoint.items()}

    added_methods = sorted(set(new_methods) - set(old_methods))
    removed_methods = sorted(set(old_methods) - set(new_methods))

    changed_methods: dict[str, dict[str, list[dict[str, str]] | list[str]]] = {}
    for method in sorted(set(old_methods) & set(new_methods)):
        old_spec = old_methods[method]
        new_spec = new_methods[method]
        field_diff = _diff_method_fields(old_spec, new_spec)
        if (
            field_diff["added_fields"]
            or field_diff["removed_fields"]
            or field_diff["changed_fields"]
        ):
            changed_methods[method] = field_diff

    return {
        "added_methods": added_methods,
        "removed_methods": removed_methods,
        "changed_methods": changed_methods,
    }


def diff_contracts(old: ApiContract, new: ApiContract) -> dict[str, object]:
    """Return a structured diff between two API contracts."""
    old_endpoints = {str(path): spec for path, spec in old.endpoints.items()}
    new_endpoints = {str(path): spec for path, spec in new.endpoints.items()}

    added_endpoints = sorted(set(new_endpoints) - set(old_endpoints))
    removed_endpoints = sorted(set(old_endpoints) - set(new_endpoints))

    changed_endpoints: dict[str, dict[str, object]] = {}
    for endpoint in sorted(set(old_endpoints) & set(new_endpoints)):
        endpoint_diff = _diff_endpoint_methods(old_endpoints[endpoint], new_endpoints[endpoint])
        if (
            endpoint_diff["added_methods"]
            or endpoint_diff["removed_methods"]
            or endpoint_diff["changed_methods"]
        ):
            changed_endpoints[endpoint] = endpoint_diff

    return {
        "added_endpoints": added_endpoints,
        "removed_endpoints": removed_endpoints,
        "changed_endpoints": changed_endpoints,
    }
