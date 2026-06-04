package flux

import (
	"context"
	"strings"
	"testing"

	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/runtime/schema"
	dynamicfake "k8s.io/client-go/dynamic/fake"
)

func newKustomizationClient(t *testing.T, obj *unstructured.Unstructured) *realFluxClient {
	t.Helper()
	scheme := runtime.NewScheme()
	listKinds := map[schema.GroupVersionResource]string{
		kustomizationGVR: "KustomizationList",
	}
	dc := dynamicfake.NewSimpleDynamicClientWithCustomListKinds(scheme, listKinds, obj)
	return &realFluxClient{dynClient: dc}
}

func kustomizationObject(namespace, name string, status map[string]interface{}) *unstructured.Unstructured {
	obj := map[string]interface{}{
		"apiVersion": "kustomize.toolkit.fluxcd.io/v1",
		"kind":       "Kustomization",
		"metadata": map[string]interface{}{
			"namespace": namespace,
			"name":      name,
		},
	}
	if status != nil {
		obj["status"] = status
	}
	return &unstructured.Unstructured{Object: obj}
}

func TestGetKustomizationStatus_LastAppliedRevision(t *testing.T) {
	obj := kustomizationObject("flux-system", "infra", map[string]interface{}{
		"lastAppliedRevision": "main@sha1:abc1234",
		"conditions": []interface{}{
			map[string]interface{}{"type": "Ready", "status": "True", "message": "Applied revision"},
		},
	})
	c := newKustomizationClient(t, obj)

	out, err := c.GetKustomizationStatus(context.Background(), "flux-system", "infra")
	if err != nil {
		t.Fatalf("GetKustomizationStatus: %v", err)
	}
	if !strings.Contains(out, "LastAppliedRevision: main@sha1:abc1234") {
		t.Errorf("expected last applied revision line, got:\n%s", out)
	}
}

func TestGetKustomizationStatus_LastAppliedRevisionAbsent(t *testing.T) {
	obj := kustomizationObject("flux-system", "infra", map[string]interface{}{
		"conditions": []interface{}{},
	})
	c := newKustomizationClient(t, obj)

	out, err := c.GetKustomizationStatus(context.Background(), "flux-system", "infra")
	if err != nil {
		t.Fatalf("GetKustomizationStatus: %v", err)
	}
	if !strings.Contains(out, "LastAppliedRevision: \n") {
		t.Errorf("expected empty last applied revision line, got:\n%s", out)
	}
}
