from __future__ import annotations

import difflib
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import yaml
from common.mcp_call import call_tool

if TYPE_CHECKING:
    from orchestrator.models import FaultEvent

    from diagnosis.models import DiagnosisDeps

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AdmissionObject:
    """A namespace-scoped admission-control object discovered in the cluster."""

    kind: str
    name: str
    namespace: str
    summary: str
    declared_in_git: bool
    git_path: str | None


@dataclass(frozen=True)
class DiagnosisContext:
    """Ground-truth state computed by Python before the diagnosis LLM runs."""

    source_branch: str
    manifest_path: str | None
    live_yaml: str
    declared_yaml: str
    diff: str
    live_pod_status: str = field(default="")
    live_admission_objects: list[AdmissionObject] = field(default_factory=list)


class ManifestPathUnresolvable(RuntimeError):
    """Raised when Flux annotations are absent and no fallback path applies."""


class ResourceKindUnresolvable(RuntimeError):
    """Raised when no recognised resource label is present in the alert."""


_LABEL_TO_KIND: tuple[tuple[str, str], ...] = (
    ("deployment", "Deployment"),
    ("statefulset", "StatefulSet"),
    ("daemonset", "DaemonSet"),
    ("pod", "Pod"),
    ("persistentvolumeclaim", "PersistentVolumeClaim"),
    ("kustomization", "Kustomization"),
)


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


_TYPED_RESULT_KEYS = ("content", "path", "sha", "pr_number", "merge_commit_sha")


def _extract_text(result: object) -> str:
    if isinstance(result, dict):
        for key in _TYPED_RESULT_KEYS:
            if key in result and len(result) <= 4:
                return str(result[key])
        raise TypeError(
            f"structured MCP result requires explicit handling: {sorted(result)}"
        )
    return str(result)


async def _resolve_source_branch(deps: DiagnosisDeps) -> str:
    result = await call_tool(
        deps.kubectl_mcp,
        "get_resource_yaml",
        {"kind": "GitRepository", "namespace": "flux-system", "name": "flux-system"},
    )
    text = _extract_text(result)
    try:
        data = yaml.safe_load(text)
        branch = (data.get("spec") or {}).get("ref", {}).get("branch", "")
        return branch or "main"
    except (yaml.YAMLError, AttributeError):
        return "main"


def extract_alert_namespace(fault: FaultEvent, default: str) -> str:
    """Return the namespace named in alert labels, else commonLabels, else default."""
    for alert in fault.alerts:
        namespace = alert.get("labels", {}).get("namespace")
        if namespace:
            return namespace
    return fault.commonLabels.get("namespace") or default


def _extract_target_host(fault: FaultEvent) -> str | None:
    for alert in fault.alerts:
        labels = alert.get("labels", {})
        if "node" in labels:
            return labels["node"]
    node = fault.commonLabels.get("node") or fault.groupLabels.get("node")
    return node or None


def _extract_systemd_unit(fault: FaultEvent) -> str | None:
    for alert in fault.alerts:
        unit = alert.get("labels", {}).get("systemd_unit") or (
            alert.get("annotations", {}).get("systemd_unit")
        )
        if unit:
            return unit
    return None


def _extract_sysctl_key(fault: FaultEvent) -> str | None:
    for alert in fault.alerts:
        key = alert.get("labels", {}).get("sysctl_key") or (
            alert.get("annotations", {}).get("sysctl_key")
        )
        if key:
            return key
    return fault.commonLabels.get("sysctl_key") or fault.groupLabels.get("sysctl_key")


def _extract_flux_annotations(live_text: str) -> tuple[str | None, str | None]:
    try:
        data = yaml.safe_load(live_text)
        metadata = data.get("metadata") or {}
        labels = metadata.get("labels") or {}
        annotations = metadata.get("annotations") or {}
        kust_name = labels.get("kustomize.toolkit.fluxcd.io/name") or annotations.get(
            "kustomize.toolkit.fluxcd.io/name"
        )
        kust_ns = labels.get(
            "kustomize.toolkit.fluxcd.io/namespace"
        ) or annotations.get("kustomize.toolkit.fluxcd.io/namespace")
        return kust_name, kust_ns
    except (yaml.YAMLError, AttributeError):
        return None, None


async def _walk_pod_to_deployment(
    deps: DiagnosisDeps, pod_yaml: str, namespace: str
) -> tuple[str, str]:
    """Resolve Deployment from pod labels first; fall back to ownerReferences walk."""
    try:
        pod_data = yaml.safe_load(pod_yaml)
        labels = (pod_data.get("metadata") or {}).get("labels") or {}
        for label_key in ("app.kubernetes.io/name", "app"):
            dep_name = labels.get(label_key)
            if dep_name:
                try:
                    dep_result = await call_tool(
                        deps.kubectl_mcp,
                        "get_resource_yaml",
                        {
                            "kind": "Deployment",
                            "namespace": namespace,
                            "name": dep_name,
                        },
                    )
                    return dep_name, _extract_text(dep_result)
                except Exception as exc:
                    log.debug(
                        "label-based Deployment lookup failed for %s, "
                        "falling back to ownerReferences: %s",
                        dep_name,
                        exc,
                    )
        owner_refs = (pod_data.get("metadata") or {}).get("ownerReferences") or []
        rs_ref = next((r for r in owner_refs if r.get("kind") == "ReplicaSet"), None)
        if not rs_ref:
            raise ManifestPathUnresolvable("Pod has no ReplicaSet ownerReference")
        rs_result = await call_tool(
            deps.kubectl_mcp,
            "get_resource_yaml",
            {"kind": "ReplicaSet", "namespace": namespace, "name": rs_ref["name"]},
        )
        rs_data = yaml.safe_load(_extract_text(rs_result))
        rs_owners = (rs_data.get("metadata") or {}).get("ownerReferences") or []
        dep_ref = next((r for r in rs_owners if r.get("kind") == "Deployment"), None)
        if not dep_ref:
            raise ManifestPathUnresolvable(
                "ReplicaSet has no Deployment ownerReference"
            )
        dep_result = await call_tool(
            deps.kubectl_mcp,
            "get_resource_yaml",
            {"kind": "Deployment", "namespace": namespace, "name": dep_ref["name"]},
        )
        return dep_ref["name"], _extract_text(dep_result)
    except ManifestPathUnresolvable:
        raise
    except Exception as exc:
        raise ManifestPathUnresolvable(
            f"pod-to-deployment resolution failed: {exc}"
        ) from exc


async def _resolve_manifest_path_k8s(
    deps: DiagnosisDeps,
    fault: FaultEvent,
    live_text: str,
    kind: str,
    namespace: str,
    resource_name_override: str | None = None,
) -> str:
    kust_name, kust_ns = _extract_flux_annotations(live_text)
    if not kust_name or not kust_ns:
        raise ManifestPathUnresolvable(
            "live resource has no Flux Kustomization annotations"
        )

    kust_result = await call_tool(
        deps.kubectl_mcp,
        "get_resource_yaml",
        {"kind": "Kustomization", "namespace": kust_ns, "name": kust_name},
    )
    kust_text = _extract_text(kust_result)
    try:
        kust_data = yaml.safe_load(kust_text)
        spec_path = (kust_data.get("spec") or {}).get("path", "")
        spec_path = spec_path.lstrip("./")
        if not spec_path:
            raise ManifestPathUnresolvable("Kustomization spec.path is absent")
    except (yaml.YAMLError, AttributeError) as exc:
        raise ManifestPathUnresolvable(
            f"Kustomization YAML parse error: {exc}"
        ) from exc

    name = (
        resource_name_override
        if resource_name_override is not None
        else _extract_resource_name(fault)
    )
    try:
        result = await call_tool(
            deps.git_mcp,
            "resolve_manifest_path",
            {
                "kustomize_path": spec_path,
                "kind": kind,
                "name": name,
                "namespace": namespace,
            },
        )
        if isinstance(result, dict) and "path" in result:
            return result["path"]
        return _extract_text(result)
    except Exception as exc:
        log.warning(
            "resolve_manifest_path failed for %s/%s under %s: %s",
            kind,
            name,
            spec_path,
            exc,
        )
        raise ManifestPathUnresolvable(
            f"{kind}/{name} not found under {spec_path}"
        ) from exc


def _extract_resource_name(fault: FaultEvent) -> str:
    for alert in fault.alerts:
        labels = alert.get("labels", {})
        for label, _ in _LABEL_TO_KIND:
            if label in labels:
                return labels[label]
        if "name" in labels:
            return labels["name"]
    return fault.commonLabels.get("name", "unknown")


def _extract_k8s_kind_namespace_name(fault: FaultEvent) -> tuple[str, str, str]:
    namespace_fallback: str | None = None
    for alert in fault.alerts:
        labels = alert.get("labels", {})
        namespace = (
            labels.get("namespace") or fault.commonLabels.get("namespace") or "default"
        )
        for label, kind in _LABEL_TO_KIND:
            if label in labels:
                return kind, namespace, labels[label]
        if "namespace" in labels and namespace_fallback is None:
            namespace_fallback = namespace
    if namespace_fallback is not None:
        return "Namespace", namespace_fallback, namespace_fallback
    label_dump = [a.get("labels", {}) for a in fault.alerts]
    raise ResourceKindUnresolvable(
        f"no recognised resource label in alert labels: {label_dump}"
    )


_KUST_RESOURCE_RE = re.compile(
    r"(?:([A-Za-z]+)(?:\.[\w.]+)?\s+\"([^\"]+)\""
    r"|([A-Za-z]+)/([^\s:]+))"
    r"\s+(?:apply failed|dry-run failed|is invalid)",
    re.IGNORECASE,
)

_QUOTA_NAME_RE = re.compile(r"exceeded quota:\s*([^\s,]+)")


def _extract_quota_names_from_events(events_text: str) -> list[str]:
    """Return deduplicated ResourceQuota names from FailedCreate event messages."""
    return list(dict.fromkeys(_QUOTA_NAME_RE.findall(events_text)))


async def _get_kustomize_spec_path(deps: DiagnosisDeps, live_text: str) -> str | None:
    """Extract the Kustomization spec.path from a live resource's Flux annotations."""
    kust_name, kust_ns = _extract_flux_annotations(live_text)
    if not kust_name or not kust_ns:
        return None
    try:
        kust_result = await call_tool(
            deps.kubectl_mcp,
            "get_resource_yaml",
            {"kind": "Kustomization", "namespace": kust_ns, "name": kust_name},
        )
        kust_data = yaml.safe_load(_extract_text(kust_result))
        spec_path = (kust_data.get("spec") or {}).get("path", "").lstrip("./")
        return spec_path or None
    except Exception as exc:
        log.debug(
            "kustomize spec.path lookup failed for %s/%s: %s",
            kust_ns,
            kust_name,
            exc,
        )
        return None


def _extract_kustomization_apply_error(
    kust_yaml_text: str,
) -> tuple[str, str | None, str | None]:
    """Return (error_message, failing_kind, failing_name) from Kustomization status.

    Prefers ReconciliationFailed/ApplyFailed conditions over DependencyNotReady so
    the agent sees the root-cause apply error rather than a stale dependency message.
    """
    try:
        data = yaml.safe_load(kust_yaml_text)
        conditions = (data.get("status") or {}).get("conditions") or []
    except (yaml.YAMLError, AttributeError):
        return "", None, None

    preferred_reasons = {"ReconciliationFailed", "ApplyFailed", "BuildFailed"}
    best_msg = ""
    for cond in conditions:
        reason = cond.get("reason", "")
        msg = cond.get("message", "")
        if reason in preferred_reasons and msg:
            best_msg = msg
            break
    if not best_msg:
        for cond in conditions:
            if cond.get("status") == "False" and cond.get("message"):
                best_msg = cond["message"]
                break

    if not best_msg:
        return "", None, None

    m = _KUST_RESOURCE_RE.search(best_msg)
    if m:
        if m.group(1):
            return best_msg, m.group(1), m.group(2)
        return best_msg, m.group(3), m.group(4)
    return best_msg, None, None


async def _fetch_admission_objects(
    deps: DiagnosisDeps,
    namespace: str,
    source_branch: str,
    kustomize_path: str | None,
) -> list[AdmissionObject]:
    """Discover ResourceQuota objects from namespace events and check git."""
    objects: list[AdmissionObject] = []

    try:
        events_result = await call_tool(
            deps.kubectl_mcp,
            "get_events",
            {"namespace": namespace, "field_selector": ""},
        )
        events_text = _extract_text(events_result)
    except Exception as exc:
        log.warning(
            "namespace events unavailable for %s, skipping admission discovery: %s",
            namespace,
            exc,
        )
        return objects

    for quota_name in _extract_quota_names_from_events(events_text):
        try:
            rq_result = await call_tool(
                deps.kubectl_mcp,
                "get_resource_yaml",
                {"kind": "ResourceQuota", "namespace": namespace, "name": quota_name},
            )
            rq_text = _extract_text(rq_result)
        except Exception as exc:
            log.debug("ResourceQuota/%s fetch failed, skipping: %s", quota_name, exc)
            continue

        declared_in_git = False
        git_path: str | None = None
        if kustomize_path:
            try:
                path_result = await call_tool(
                    deps.git_mcp,
                    "resolve_manifest_path",
                    {
                        "kustomize_path": kustomize_path,
                        "kind": "ResourceQuota",
                        "name": quota_name,
                        "namespace": namespace,
                    },
                )
                git_path = (
                    path_result.get("path")
                    if isinstance(path_result, dict)
                    else _extract_text(path_result)
                )
                declared_in_git = bool(git_path)
            except Exception as exc:
                log.debug(
                    "resolve_manifest_path failed for ResourceQuota/%s, skipping: %s",
                    quota_name,
                    exc,
                )

        objects.append(
            AdmissionObject(
                kind="ResourceQuota",
                name=quota_name,
                namespace=namespace,
                summary=rq_text[:500],
                declared_in_git=declared_in_git,
                git_path=git_path,
            )
        )

    return objects


async def _fetch_pod_status(deps: DiagnosisDeps, namespace: str) -> str:
    """Pre-fetch pods and namespace events for K8s workload alerts."""
    parts: list[str] = []
    try:
        pods_result = await call_tool(
            deps.kubectl_mcp, "get_pods", {"namespace": namespace}
        )
        parts.append("=== Pods ===\n" + _extract_text(pods_result))
    except Exception as exc:
        parts.append(f"=== Pods (error) ===\n{exc}")
    try:
        events_result = await call_tool(
            deps.kubectl_mcp,
            "get_events",
            {"namespace": namespace, "field_selector": ""},
        )
        parts.append("=== Events ===\n" + _extract_text(events_result))
    except Exception as exc:
        parts.append(f"=== Events (error) ===\n{exc}")
    return "\n\n".join(parts)


async def build_diagnosis_context(
    deps: DiagnosisDeps, fault: FaultEvent
) -> DiagnosisContext:
    source_branch = await _resolve_source_branch(deps)
    await call_tool(
        deps.git_mcp,
        "clone_repo",
        {"run_id": deps.run_id, "base_branch": source_branch},
    )
    target_host = _extract_target_host(fault)

    if target_host:
        manifest_path_result = await call_tool(
            deps.nixos_mcp,
            "get_nix_path",
            {"hostname": target_host},
        )
        manifest_path = _extract_text(manifest_path_result)

        systemd_unit = _extract_systemd_unit(fault)
        sysctl_key = _extract_sysctl_key(fault)
        if systemd_unit:
            live_result = await call_tool(
                deps.nixos_mcp,
                "get_systemd_status",
                {"host": target_host, "unit": systemd_unit},
            )
        elif sysctl_key:
            live_result = await call_tool(
                deps.nixos_mcp,
                "get_sysctl",
                {"host": target_host, "key": sysctl_key},
            )
        else:
            live_result = await call_tool(
                deps.nixos_mcp,
                "get_journal",
                {"host": target_host, "lines": 50},
            )
        live_yaml = _extract_text(live_result)

        declared_result = await call_tool(
            deps.git_mcp,
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

    kind, namespace, name = _extract_k8s_kind_namespace_name(fault)

    if kind == "Namespace":
        alert_labels = [a.get("labels", {}) for a in fault.alerts]
        live_yaml = f"namespace: {namespace}\nalert_labels: {alert_labels}"
        return DiagnosisContext(
            source_branch=source_branch,
            manifest_path=None,
            live_yaml=live_yaml,
            declared_yaml="",
            diff="",
        )

    if kind == "Kustomization":
        kust_raw_result = await call_tool(
            deps.kubectl_mcp,
            "get_resource_yaml",
            {"kind": "Kustomization", "namespace": namespace, "name": name},
        )
        kust_raw_text = _extract_text(kust_raw_result)
        kust_status_result = await call_tool(
            deps.flux_mcp,
            "get_kustomization_status",
            {"namespace": namespace, "name": name},
        )
        kust_status_text = _extract_text(kust_status_result)

        apply_error, failing_kind, failing_name = _extract_kustomization_apply_error(
            kust_raw_text
        )

        if failing_kind and failing_name:
            try:
                failing_live_result = await call_tool(
                    deps.kubectl_mcp,
                    "get_resource_yaml",
                    {
                        "kind": failing_kind,
                        "namespace": namespace,
                        "name": failing_name,
                    },
                )
                failing_live_yaml = _extract_text(failing_live_result)
            except Exception as exc:
                log.debug(
                    "failing %s/%s live state unavailable: %s",
                    failing_kind,
                    failing_name,
                    exc,
                )
                failing_live_yaml = ""

            kust_data = yaml.safe_load(kust_raw_text) if kust_raw_text else {}
            spec_path = (
                (kust_data.get("spec") or {}).get("path", "").lstrip("./")
                if isinstance(kust_data, dict)
                else ""
            )
            child_manifest_path: str | None = None
            child_declared_yaml = ""
            if spec_path and failing_live_yaml:
                try:
                    path_result = await call_tool(
                        deps.git_mcp,
                        "resolve_manifest_path",
                        {
                            "kustomize_path": spec_path,
                            "kind": failing_kind,
                            "name": failing_name,
                            "namespace": namespace,
                        },
                    )
                    child_manifest_path = (
                        path_result.get("path")
                        if isinstance(path_result, dict)
                        else _extract_text(path_result)
                    )
                    declared_result = await call_tool(
                        deps.git_mcp,
                        "read_file",
                        {"branch": source_branch, "path": child_manifest_path},
                    )
                    child_declared_yaml = _extract_text(declared_result)
                except Exception as exc:
                    log.debug(
                        "child manifest resolution failed for %s/%s under %s: %s",
                        failing_kind,
                        failing_name,
                        spec_path,
                        exc,
                    )
                    child_manifest_path = None

            live_yaml_parts = [kust_status_text]
            if apply_error:
                live_yaml_parts.append(f"\nApply error:\n{apply_error}")
            if failing_live_yaml:
                live_yaml_parts.append(
                    f"\n{failing_kind}/{failing_name} live state:\n{failing_live_yaml}"
                )
            child_diff = (
                _compute_diff(failing_live_yaml, child_declared_yaml)
                if failing_live_yaml and child_declared_yaml
                else ""
            )
            return DiagnosisContext(
                source_branch=source_branch,
                manifest_path=child_manifest_path,
                live_yaml="\n".join(live_yaml_parts),
                declared_yaml=child_declared_yaml,
                diff=child_diff,
            )

        return DiagnosisContext(
            source_branch=source_branch,
            manifest_path=None,
            live_yaml=kust_status_text,
            declared_yaml="",
            diff="",
        )

    live_result = await call_tool(
        deps.kubectl_mcp,
        "get_resource_yaml",
        {"kind": kind, "namespace": namespace, "name": name},
    )
    live_yaml = _extract_text(live_result)

    resource_name_override: str | None = None
    resolved_kind = kind
    if kind == "Pod":
        try:
            dep_name, dep_yaml = await _walk_pod_to_deployment(
                deps, live_yaml, namespace
            )
            live_yaml = dep_yaml
            resource_name_override = dep_name
            resolved_kind = "Deployment"
        except ManifestPathUnresolvable as exc:
            log.warning("pod-to-deployment walk failed, proceeding as Pod: %s", exc)

    try:
        manifest_path: str = await _resolve_manifest_path_k8s(
            deps, fault, live_yaml, resolved_kind, namespace, resource_name_override
        )
    except ManifestPathUnresolvable:
        if resolved_kind == "Pod":
            live_pod_status = await _fetch_pod_status(deps, namespace)
            return DiagnosisContext(
                source_branch=source_branch,
                manifest_path=None,
                live_yaml=live_yaml,
                declared_yaml="",
                diff="",
                live_pod_status=live_pod_status,
            )
        raise

    try:
        declared_result = await call_tool(
            deps.git_mcp,
            "read_file",
            {"branch": source_branch, "path": manifest_path},
        )
        declared_yaml = _extract_text(declared_result)
    except Exception as exc:
        raise ManifestPathUnresolvable(
            f"declared manifest unreadable at {manifest_path}: {exc}"
        ) from exc

    diff = _compute_diff(live_yaml, declared_yaml)
    live_pod_status = await _fetch_pod_status(deps, namespace)
    kustomize_path = await _get_kustomize_spec_path(deps, live_yaml)
    live_admission_objects = await _fetch_admission_objects(
        deps, namespace, source_branch, kustomize_path
    )
    return DiagnosisContext(
        source_branch=source_branch,
        manifest_path=manifest_path,
        live_yaml=live_yaml,
        declared_yaml=declared_yaml,
        diff=diff,
        live_pod_status=live_pod_status,
        live_admission_objects=live_admission_objects,
    )
