package main

import rego.v1

allowed_kinds := {"Deployment", "ConfigMap"}

deny contains msg if {
	not allowed_kinds[input.kind]
	msg := sprintf("resource kind %q is not in the allowlist (allowed: Deployment, ConfigMap)", [input.kind])
}

deny contains msg if {
	not input.metadata.namespace
	msg := "cluster-scoped resources are not permitted; declare metadata.namespace"
}
