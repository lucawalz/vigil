from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from orchestrator.models import FaultEvent

    from diagnosis.models import DiagnosisDeps


@dataclass(frozen=True)
class DiagnosisContext:
    """Ground-truth state computed by Python before the diagnosis LLM runs."""

    source_branch: str
    manifest_path: str | None
    live_yaml: str
    declared_yaml: str
    diff: str


class ManifestPathUnresolvable(RuntimeError):
    """Raised when Flux annotations are absent and no fallback path applies."""


def _compute_diff(live: str, declared: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            live.splitlines(),
            declared.splitlines(),
            fromfile="live",
            tofile="declared",
            lineterm="",
        )
    )


def _extract_text(result: object) -> str:
    if isinstance(result, dict) and "content" in result:
        return str(result["content"])
    return str(result)


async def _resolve_source_branch(deps: DiagnosisDeps) -> str:
    result = await deps.kubectl_mcp.direct_call_tool(
        "get_resource_yaml",
        {"kind": "GitRepository", "namespace": "flux-system", "name": "flux-system"},
    )
    text = _extract_text(result)
    try:
        data = yaml.safe_load(text)
        branch = (data.get("spec") or {}).get("ref", {}).get("branch", "")
        return branch or "main"
    except Exception:
        return "main"


def _extract_target_host(fault: FaultEvent) -> str | None:
    for alert in fault.alerts:
        labels = alert.get("labels", {})
        if "node" in labels:
            return labels["node"]
    node = fault.commonLabels.get("node") or fault.groupLabels.get("node")
    return node or None


def _extract_systemd_unit(fault: FaultEvent) -> str:
    for alert in fault.alerts:
        unit = alert.get("labels", {}).get("systemd_unit") or (
            alert.get("annotations", {}).get("systemd_unit")
        )
        if unit:
            return unit
    return "vigil-auto-reconcile.service"


_KUST_SUFFIX = "_kustomize.toolkit.fluxcd.io_Kustomization"


def _extract_flux_annotations(live_text: str) -> tuple[str | None, str | None]:
    try:
        data = yaml.safe_load(live_text)
        metadata = data.get("metadata") or {}
        # Flux v2 puts tracking identifiers in labels; check annotations as fallback
        labels = metadata.get("labels") or {}
        annotations = metadata.get("annotations") or {}
        kust_name = labels.get("kustomize.toolkit.fluxcd.io/name") or annotations.get(
            "kustomize.toolkit.fluxcd.io/name"
        )
        kust_ns = labels.get(
            "kustomize.toolkit.fluxcd.io/namespace"
        ) or annotations.get("kustomize.toolkit.fluxcd.io/namespace")
        return kust_name, kust_ns
    except Exception:
        return None, None


def _parse_child_kust_entries(kust_data: dict) -> list[tuple[str, str]]:
    entries = (
        ((kust_data.get("status") or {}).get("inventory") or {}).get("entries") or []
    )
    result = []
    for entry in entries:
        entry_id = entry.get("id", "")
        if not entry_id.endswith(_KUST_SUFFIX):
            continue
        ns_name = entry_id[: -len(_KUST_SUFFIX)]
        parts = ns_name.split("_", 1)
        if len(parts) == 2:
            result.append((parts[0], parts[1]))
    return result


async def _resolve_manifest_path_k8s(
    deps: DiagnosisDeps,
    fault: FaultEvent,
    live_text: str,
    source_branch: str,
) -> str:
    kust_name, kust_ns = _extract_flux_annotations(live_text)
    if not kust_name or not kust_ns:
        raise ManifestPathUnresolvable(
            "live resource has no Flux Kustomization annotations"
        )

    kust_result = await deps.kubectl_mcp.direct_call_tool(
        "get_resource_yaml",
        {"kind": "Kustomization", "namespace": kust_ns, "name": kust_name},
    )
    kust_text = _extract_text(kust_result)
    try:
        kust_data = yaml.safe_load(kust_text)
        spec_path = (kust_data.get("spec") or {}).get("path", "").lstrip("./")
        if not spec_path:
            raise ManifestPathUnresolvable("Kustomization spec.path is absent")
    except (yaml.YAMLError, AttributeError) as exc:
        msg = f"Kustomization YAML parse error: {exc}"
        raise ManifestPathUnresolvable(msg) from exc

    resource_name = _extract_resource_name(fault)

    direct_path = f"{spec_path}/{resource_name}.yaml"
    try:
        await deps.git_mcp.direct_call_tool(
            "read_file", {"branch": source_branch, "path": direct_path}
        )
        return direct_path
    except Exception:
        pass

    for child_ns, child_name in _parse_child_kust_entries(kust_data):
        if child_name == kust_name and child_ns == kust_ns:
            continue
        try:
            child_res = await deps.kubectl_mcp.direct_call_tool(
                "get_resource_yaml",
                {"kind": "Kustomization", "namespace": child_ns, "name": child_name},
            )
            child_data = yaml.safe_load(_extract_text(child_res)) or {}
            child_spec_path = (child_data.get("spec") or {}).get("path", "").lstrip("./")
            if not child_spec_path:
                continue
            candidate = f"{child_spec_path}/{resource_name}.yaml"
            await deps.git_mcp.direct_call_tool(
                "read_file", {"branch": source_branch, "path": candidate}
            )
            return candidate
        except Exception:
            continue

    raise ManifestPathUnresolvable(
        f"manifest {resource_name}.yaml not found under any Kustomization path"
    )


def _extract_resource_name(fault: FaultEvent) -> str:
    for alert in fault.alerts:
        labels = alert.get("labels", {})
        for key in ("deployment", "pod", "statefulset", "daemonset", "name"):
            if key in labels:
                return labels[key]
    return fault.commonLabels.get("deployment", "unknown")


def _extract_k8s_kind_namespace_name(fault: FaultEvent) -> tuple[str, str, str]:
    for alert in fault.alerts:
        labels = alert.get("labels", {})
        namespace = (
            labels.get("namespace") or fault.commonLabels.get("namespace") or "default"
        )
        if "deployment" in labels:
            return "Deployment", namespace, labels["deployment"]
        if "pod" in labels:
            return "Pod", namespace, labels["pod"]
        if "statefulset" in labels:
            return "StatefulSet", namespace, labels["statefulset"]
    namespace = fault.commonLabels.get("namespace", "default")
    name = fault.commonLabels.get("deployment", "unknown")
    return "Deployment", namespace, name


async def build_diagnosis_context(
    deps: DiagnosisDeps, fault: FaultEvent
) -> DiagnosisContext:
    source_branch = await _resolve_source_branch(deps)
    target_host = _extract_target_host(fault)

    if target_host:
        manifest_path = f"infra/nixos/hosts/{target_host}.nix"
        systemd_unit = _extract_systemd_unit(fault)

        live_result = await deps.nixos_mcp.direct_call_tool(
            "get_systemd_status",
            {"host": target_host, "unit": systemd_unit},
        )
        live_yaml = _extract_text(live_result)

        declared_result = await deps.nixos_mcp.direct_call_tool(
            "dry_build",
            {"host": target_host},
        )
        declared_yaml = _extract_text(declared_result)

        diff = _compute_diff(live_yaml, declared_yaml)
        return DiagnosisContext(
            source_branch=source_branch,
            manifest_path=manifest_path,
            live_yaml=live_yaml,
            declared_yaml=declared_yaml,
            diff=diff,
        )

    kind, namespace, name = _extract_k8s_kind_namespace_name(fault)
    live_result = await deps.kubectl_mcp.direct_call_tool(
        "get_resource_yaml",
        {"kind": kind, "namespace": namespace, "name": name},
    )
    live_yaml = _extract_text(live_result)

    manifest_path = await _resolve_manifest_path_k8s(
        deps, fault, live_yaml, source_branch
    )

    declared_result = await deps.git_mcp.direct_call_tool(
        "read_file",
        {"branch": source_branch, "path": manifest_path},
    )
    declared_yaml = _extract_text(declared_result)

    diff = _compute_diff(live_yaml, declared_yaml)
    return DiagnosisContext(
        source_branch=source_branch,
        manifest_path=manifest_path,
        live_yaml=live_yaml,
        declared_yaml=declared_yaml,
        diff=diff,
    )
