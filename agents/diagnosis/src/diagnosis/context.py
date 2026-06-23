from __future__ import annotations

import difflib
import logging
import posixpath
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import yaml
from common.flux_status import coerce_flux_status
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
    live_services: str = field(default="")


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


def extract_alert_name(fault: FaultEvent) -> str | None:
    """Return the alertname named in the fault event, or None."""
    for alert in fault.alerts:
        name = alert.get("labels", {}).get("alertname")
        if name:
            return name
    return fault.commonLabels.get("alertname") or fault.groupLabels.get("alertname")


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


def _declared_sysctl_value(declared_nix: str, key: str) -> str | None:
    match = re.search(r'"' + re.escape(key) + r'"\s*=\s*([^;]+);', declared_nix)
    if not match:
        return None
    return match.group(1).split()[-1].strip('"')


_MAX_NIX_IMPORT_DEPTH = 5
_NIX_IMPORTS_BLOCK_RE = re.compile(r"imports\s*=\s*\[(.*?)\]", re.DOTALL)
_NIX_COMMENT_RE = re.compile(r"#.*")


def _parse_nix_import_entries(entry_text: str) -> list[str]:
    """Return the raw paths listed in a Nix ``imports = [ ... ];`` block."""
    block = _NIX_IMPORTS_BLOCK_RE.search(entry_text)
    if not block:
        return []
    stripped = _NIX_COMMENT_RE.sub("", block.group(1))
    return stripped.split()


def _resolve_nix_import_path(entry_path: str, entry: str) -> str:
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(entry_path), entry))
    if not resolved.endswith(".nix"):
        resolved = posixpath.join(resolved, "default.nix")
    return resolved


async def _resolve_nix_imports(
    deps: DiagnosisDeps,
    source_branch: str,
    entry_path: str,
    entry_text: str,
    *,
    visited: set[str],
    depth: int,
) -> str:
    """Concatenate the bodies of every Nix module reachable via ``imports``.

    A host entrypoint declares OS state by importing modules, so the declaration
    that drifted often lives in a transitively imported file rather than the
    host file itself; this walks the import graph to surface it.
    """
    if depth >= _MAX_NIX_IMPORT_DEPTH:
        return ""
    bodies: list[str] = []
    for entry in _parse_nix_import_entries(entry_text):
        resolved = _resolve_nix_import_path(entry_path, entry)
        if resolved in visited:
            continue
        visited.add(resolved)
        try:
            result = await call_tool(
                deps.git_mcp,
                "read_file",
                {"branch": source_branch, "path": resolved},
            )
            body = _extract_text(result)
        except Exception as exc:
            # An optional or absent import must never abort diagnosis.
            log.debug("nix import %s unreadable, skipping: %s", resolved, exc)
            continue
        bodies.append(body)
        nested = await _resolve_nix_imports(
            deps,
            source_branch,
            resolved,
            body,
            visited=visited,
            depth=depth + 1,
        )
        if nested:
            bodies.append(nested)
    return "\n".join(bodies)


def extract_systemd_unit(fault: FaultEvent) -> str | None:
    """Return the systemd unit named in the alert, or None."""
    return _extract_systemd_unit(fault)


def declared_sysctl_value(declared_nix: str, key: str) -> str | None:
    """Return the value declared for a sysctl key in a NixOS config, or None.

    The orchestrator derives the recovery pass-value from declarative git truth
    rather than the agent, keeping any scenario-supplied value out of diagnosis.
    """
    return _declared_sysctl_value(declared_nix, key)


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


def _deployment_name_from_pod(pod_name: str) -> str:
    """Return the Deployment name a pod belongs to.

    Deployment-managed pods are named ``<deployment>-<replicaset-hash>-<pod-hash>``,
    so dropping the two generated suffixes recovers the workload that owns them.
    """
    parts = pod_name.rsplit("-", 2)
    return parts[0] if len(parts) == 3 else pod_name


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
    r"|([A-Za-z]+)/(?:([^\s:/]+)/)?([^\s:/]+))"
    r"\s+(?:apply failed|dry-run failed|is invalid)",
    re.IGNORECASE,
)

_QUOTA_NAME_RE = re.compile(r"exceeded quota:\s*([^\s,]+)")

_ADMISSION_KINDS: tuple[str, ...] = ("ResourceQuota", "LimitRange")
_ADMISSION_SUMMARY_MAX_CHARS = 500


def _extract_quota_names_from_events(events_text: str) -> list[str]:
    """Return deduplicated ResourceQuota names from FailedCreate event messages."""
    return list(dict.fromkeys(_QUOTA_NAME_RE.findall(events_text)))


def _parse_admission_list(list_yaml: str) -> list[dict]:
    """Return item dicts from a kubectl List YAML, tolerating malformed input."""
    try:
        data = yaml.safe_load(list_yaml)
    except yaml.YAMLError:
        return []
    if not isinstance(data, dict):
        return []
    items = data.get("items")
    return [item for item in items if isinstance(item, dict)] if items else []


async def _resolve_admission_git_path(
    deps: DiagnosisDeps,
    kind: str,
    name: str,
    namespace: str,
    kustomize_path: str | None,
) -> str | None:
    """Return the git manifest path for an admission object, or None if absent."""
    if not kustomize_path:
        return None
    try:
        path_result = await call_tool(
            deps.git_mcp,
            "resolve_manifest_path",
            {
                "kustomize_path": kustomize_path,
                "kind": kind,
                "name": name,
                "namespace": namespace,
            },
        )
        git_path = (
            path_result.get("path")
            if isinstance(path_result, dict)
            else _extract_text(path_result)
        )
        return git_path or None
    except Exception as exc:
        log.debug(
            "resolve_manifest_path failed for %s/%s, treating as out-of-band: %s",
            kind,
            name,
            exc,
        )
        return None


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
        return best_msg, m.group(3), m.group(5)
    return best_msg, None, None


async def _list_admission_objects(
    deps: DiagnosisDeps,
    namespace: str,
    kustomize_path: str | None,
) -> list[AdmissionObject] | None:
    """List live admission objects in the namespace; None if every kind list fails."""
    objects: list[AdmissionObject] = []
    any_listed = False
    for kind in _ADMISSION_KINDS:
        try:
            list_result = await call_tool(
                deps.kubectl_mcp,
                "get_resource_yaml",
                {"kind": kind, "namespace": namespace, "name": ""},
            )
            list_text = _extract_text(list_result)
        except Exception as exc:
            log.debug("listing %s in %s failed: %s", kind, namespace, exc)
            continue
        any_listed = True
        for item in _parse_admission_list(list_text):
            name = (item.get("metadata") or {}).get("name", "")
            if not name:
                continue
            git_path = await _resolve_admission_git_path(
                deps, kind, name, namespace, kustomize_path
            )
            objects.append(
                AdmissionObject(
                    kind=kind,
                    name=name,
                    namespace=namespace,
                    summary=yaml.safe_dump(item)[:_ADMISSION_SUMMARY_MAX_CHARS],
                    declared_in_git=git_path is not None,
                    git_path=git_path,
                )
            )
    return objects if any_listed else None


async def _discover_admission_objects_from_events(
    deps: DiagnosisDeps,
    namespace: str,
    kustomize_path: str | None,
) -> list[AdmissionObject]:
    """Fall back to naming ResourceQuotas from namespace events when listing fails."""
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
        git_path = await _resolve_admission_git_path(
            deps, "ResourceQuota", quota_name, namespace, kustomize_path
        )
        objects.append(
            AdmissionObject(
                kind="ResourceQuota",
                name=quota_name,
                namespace=namespace,
                summary=rq_text[:_ADMISSION_SUMMARY_MAX_CHARS],
                declared_in_git=git_path is not None,
                git_path=git_path,
            )
        )
    return objects


async def _fetch_admission_objects(
    deps: DiagnosisDeps,
    namespace: str,
    kustomize_path: str | None,
) -> list[AdmissionObject]:
    """Surface live admission objects in the namespace, even ones with no events.

    Listing exposes out-of-band ResourceQuotas and LimitRanges that emit no
    FailedCreate events; event-based discovery only supplements when listing fails.
    """
    listed = await _list_admission_objects(deps, namespace, kustomize_path)
    if listed is not None:
        return listed
    return await _discover_admission_objects_from_events(
        deps, namespace, kustomize_path
    )


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


_SERVICES_UNAVAILABLE_MARKER = "(services unavailable)"


async def _fetch_services(deps: DiagnosisDeps, namespace: str) -> str:
    """List Services in the namespace so agents can resolve real upstream hosts.

    A proxy whose backend URL was zeroed has no host to restore from git, so the
    set of live Services is the only ground truth for a resolvable upstream.
    """
    try:
        result = await call_tool(
            deps.kubectl_mcp,
            "get_resource_yaml",
            {"kind": "Service", "namespace": namespace, "name": ""},
        )
        return _extract_text(result)
    except Exception as exc:
        log.debug("listing Services in %s failed: %s", namespace, exc)
        return _SERVICES_UNAVAILABLE_MARKER


async def _build_os_context(
    deps: DiagnosisDeps,
    fault: FaultEvent,
    source_branch: str,
    target_host: str,
) -> DiagnosisContext:
    manifest_path_result = await call_tool(
        deps.nixos_mcp,
        "get_nix_path",
        {"hostname": target_host},
    )
    manifest_path = _extract_text(manifest_path_result)

    systemd_unit = _extract_systemd_unit(fault)
    if systemd_unit:
        live_result = await call_tool(
            deps.nixos_mcp,
            "get_systemd_status",
            {"host": target_host, "unit": systemd_unit},
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

    imported = await _resolve_nix_imports(
        deps,
        source_branch,
        manifest_path,
        declared_yaml,
        visited={manifest_path},
        depth=0,
    )
    declared_full = declared_yaml + ("\n" + imported if imported else "")

    diff = _compute_diff(live_yaml, declared_full)
    return DiagnosisContext(
        source_branch=source_branch,
        manifest_path=manifest_path,
        live_yaml=live_yaml,
        declared_yaml=declared_full,
        diff=diff,
    )


async def _build_namespace_context(
    deps: DiagnosisDeps,
    fault: FaultEvent,
    source_branch: str,
    namespace: str,
) -> DiagnosisContext:
    alert_labels = [a.get("labels", {}) for a in fault.alerts]
    live_yaml = f"namespace: {namespace}\nalert_labels: {alert_labels}"
    live_pod_status = await _fetch_pod_status(deps, namespace)
    live_admission_objects = await _fetch_admission_objects(deps, namespace, None)
    return DiagnosisContext(
        source_branch=source_branch,
        manifest_path=None,
        live_yaml=live_yaml,
        declared_yaml="",
        diff="",
        live_pod_status=live_pod_status,
        live_admission_objects=live_admission_objects,
    )


async def _build_kustomization_context(
    deps: DiagnosisDeps,
    source_branch: str,
    namespace: str,
    name: str,
) -> DiagnosisContext:
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
    kust_status = coerce_flux_status(kust_status_result)
    kust_status_text = (
        f"Kustomization: {kust_status.get('namespace', '')}/"
        f"{kust_status.get('name', '')}\n"
        f"Ready: {kust_status.get('ready')}\n"
        f"Reason: {kust_status.get('reason', '')}\n"
        f"Message: {kust_status.get('message', '')}\n"
        f"LastAppliedRevision: {kust_status.get('revision', '')}"
    )

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


async def _build_workload_context(
    deps: DiagnosisDeps,
    fault: FaultEvent,
    source_branch: str,
    kind: str,
    namespace: str,
    name: str,
) -> DiagnosisContext:
    resource_name_override: str | None = None
    resolved_kind = kind
    try:
        live_result = await call_tool(
            deps.kubectl_mcp,
            "get_resource_yaml",
            {"kind": kind, "namespace": namespace, "name": name},
        )
        live_yaml = _extract_text(live_result)
    except Exception as exc:
        if kind != "Pod":
            raise
        workload = _deployment_name_from_pod(name)
        try:
            dep_result = await call_tool(
                deps.kubectl_mcp,
                "get_resource_yaml",
                {"kind": "Deployment", "namespace": namespace, "name": workload},
            )
        except Exception:
            log.warning(
                "pod %s and workload %s both unresolved, using live pod status: %s",
                name,
                workload,
                exc,
            )
            return DiagnosisContext(
                source_branch=source_branch,
                manifest_path=None,
                live_yaml="",
                declared_yaml="",
                diff="",
                live_pod_status=await _fetch_pod_status(deps, namespace),
                live_services=await _fetch_services(deps, namespace),
            )
        live_yaml = _extract_text(dep_result)
        resource_name_override = workload
        resolved_kind = "Deployment"
        log.warning("pod %s gone, diagnosed via Deployment/%s: %s", name, workload, exc)

    if resolved_kind == "Pod":
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
                live_services=await _fetch_services(deps, namespace),
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
    live_services = await _fetch_services(deps, namespace)
    kustomize_path = await _get_kustomize_spec_path(deps, live_yaml)
    live_admission_objects = await _fetch_admission_objects(
        deps, namespace, kustomize_path
    )
    return DiagnosisContext(
        source_branch=source_branch,
        manifest_path=manifest_path,
        live_yaml=live_yaml,
        declared_yaml=declared_yaml,
        diff=diff,
        live_pod_status=live_pod_status,
        live_admission_objects=live_admission_objects,
        live_services=live_services,
    )


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
        return await _build_os_context(deps, fault, source_branch, target_host)

    kind, namespace, name = _extract_k8s_kind_namespace_name(fault)

    if kind == "Namespace":
        return await _build_namespace_context(deps, fault, source_branch, namespace)

    if kind == "Kustomization":
        return await _build_kustomization_context(deps, source_branch, namespace, name)

    return await _build_workload_context(
        deps, fault, source_branch, kind, namespace, name
    )
