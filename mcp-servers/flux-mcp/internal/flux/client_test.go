package flux

import (
	"context"
	"encoding/json"
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

type fluxStatusOut struct {
	Found    bool   `json:"found"`
	Ready    *bool  `json:"ready"`
	Reason   string `json:"reason"`
	Message  string `json:"message"`
	Revision string `json:"revision"`
}

func TestGetKustomizationStatus_ReadyWithMessageIsTrue(t *testing.T) {
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
	var got fluxStatusOut
	if err := json.Unmarshal([]byte(out), &got); err != nil {
		t.Fatalf("output not valid JSON: %v\n%s", err, out)
	}
	if !got.Found {
		t.Errorf("expected found=true, got: %s", out)
	}
	if got.Ready == nil || !*got.Ready {
		t.Errorf("expected ready=true for a Ready condition carrying a message, got: %s", out)
	}
	if got.Revision != "main@sha1:abc1234" {
		t.Errorf("expected revision main@sha1:abc1234, got: %s", out)
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
	var got fluxStatusOut
	if err := json.Unmarshal([]byte(out), &got); err != nil {
		t.Fatalf("output not valid JSON: %v\n%s", err, out)
	}
	if got.Revision != "" {
		t.Errorf("expected empty revision, got: %q", got.Revision)
	}
	if got.Ready != nil {
		t.Errorf("expected ready=null with no Ready condition, got: %v", *got.Ready)
	}
}

func gitRepositoryClient(t *testing.T, obj *unstructured.Unstructured) *realFluxClient {
	t.Helper()
	scheme := runtime.NewScheme()
	listKinds := map[schema.GroupVersionResource]string{
		gitRepositoryGVR: "GitRepositoryList",
	}
	dc := dynamicfake.NewSimpleDynamicClientWithCustomListKinds(scheme, listKinds, obj)
	return &realFluxClient{dynClient: dc}
}

func TestGetGitRepositoryStatus_ArtifactRevision(t *testing.T) {
	obj := &unstructured.Unstructured{Object: map[string]interface{}{
		"apiVersion": "source.toolkit.fluxcd.io/v1",
		"kind":       "GitRepository",
		"metadata":   map[string]interface{}{"namespace": "flux-system", "name": "flux-system"},
		"status": map[string]interface{}{
			"artifact": map[string]interface{}{"revision": "main@sha1:def5678"},
			"conditions": []interface{}{
				map[string]interface{}{"type": "Ready", "status": "True", "message": "stored artifact"},
			},
		},
	}}
	c := gitRepositoryClient(t, obj)

	out, err := c.GetGitRepositoryStatus(context.Background(), "flux-system", "flux-system")
	if err != nil {
		t.Fatalf("GetGitRepositoryStatus: %v", err)
	}
	var got fluxStatusOut
	if err := json.Unmarshal([]byte(out), &got); err != nil {
		t.Fatalf("output not valid JSON: %v\n%s", err, out)
	}
	if got.Revision != "main@sha1:def5678" {
		t.Errorf("expected artifact revision main@sha1:def5678, got: %s", out)
	}
	if got.Ready == nil || !*got.Ready {
		t.Errorf("expected ready=true, got: %s", out)
	}
}
