package k8s

import (
	"testing"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	kubefake "k8s.io/client-go/kubernetes/fake"
)

func fakeClientWithResources(groups []*metav1.APIResourceList) *realK8sClient {
	cs := kubefake.NewSimpleClientset()
	cs.Resources = groups
	return &realK8sClient{cs: cs}
}

var testResources = []*metav1.APIResourceList{
	{
		GroupVersion: "v1",
		APIResources: []metav1.APIResource{
			{Kind: "ConfigMap", Name: "configmaps"},
			{Kind: "Pod", Name: "pods"},
		},
	},
	{
		GroupVersion: "apps/v1",
		APIResources: []metav1.APIResource{
			{Kind: "Deployment", Name: "deployments"},
			{Kind: "StatefulSet", Name: "statefulsets"},
		},
	},
	{
		GroupVersion: "kustomize.toolkit.fluxcd.io/v1",
		APIResources: []metav1.APIResource{
			{Kind: "Kustomization", Name: "kustomizations"},
		},
	},
}

func TestResolveKind_NonCoreKind(t *testing.T) {
	c := fakeClientWithResources(testResources)
	gvk, err := c.resolveKind("Deployment")
	if err != nil {
		t.Fatalf("resolveKind: %v", err)
	}
	if gvk.Group != "apps" || gvk.Version != "v1" || gvk.Kind != "Deployment" {
		t.Errorf("got %v, want apps/v1 Deployment", gvk)
	}
}

func TestResolveKind_CoreKind(t *testing.T) {
	c := fakeClientWithResources(testResources)
	gvk, err := c.resolveKind("ConfigMap")
	if err != nil {
		t.Fatalf("resolveKind: %v", err)
	}
	if gvk.Group != "" || gvk.Version != "v1" || gvk.Kind != "ConfigMap" {
		t.Errorf("got %v, want /v1 ConfigMap", gvk)
	}
}

func TestResolveKind_CRD(t *testing.T) {
	c := fakeClientWithResources(testResources)
	gvk, err := c.resolveKind("Kustomization")
	if err != nil {
		t.Fatalf("resolveKind: %v", err)
	}
	if gvk.Group != "kustomize.toolkit.fluxcd.io" || gvk.Version != "v1" || gvk.Kind != "Kustomization" {
		t.Errorf("got %v, want kustomize.toolkit.fluxcd.io/v1 Kustomization", gvk)
	}
}

func TestResolveKind_UnknownKind(t *testing.T) {
	c := fakeClientWithResources(testResources)
	_, err := c.resolveKind("Foo")
	if err == nil {
		t.Fatal("expected error for unknown kind, got nil")
	}
}
