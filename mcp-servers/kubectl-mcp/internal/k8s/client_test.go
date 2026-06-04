package k8s

import (
	"context"
	"encoding/json"
	"testing"

	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
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

func int32Ptr(v int32) *int32 { return &v }

func TestRolloutStatus_HealthyDeployment(t *testing.T) {
	dep := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{Name: "vigil-app", Namespace: "default", Generation: 7},
		Spec:       appsv1.DeploymentSpec{Replicas: int32Ptr(1)},
		Status: appsv1.DeploymentStatus{
			ObservedGeneration: 7,
			Replicas:           1,
			UpdatedReplicas:    1,
			ReadyReplicas:      1,
			AvailableReplicas:  1,
			Conditions: []appsv1.DeploymentCondition{
				{Type: appsv1.DeploymentAvailable, Status: corev1.ConditionTrue, Reason: "MinimumReplicasAvailable"},
				{Type: appsv1.DeploymentProgressing, Status: corev1.ConditionTrue, Reason: "NewReplicaSetAvailable"},
			},
		},
	}
	c := &realK8sClient{cs: kubefake.NewSimpleClientset(dep)}

	out, err := c.RolloutStatus(context.Background(), "default", "vigil-app")
	if err != nil {
		t.Fatalf("RolloutStatus: %v", err)
	}
	var ws workloadStatus
	if err := json.Unmarshal([]byte(out), &ws); err != nil {
		t.Fatalf("unmarshal: %v; raw=%s", err, out)
	}
	if ws.Kind != "Deployment" || !ws.Found {
		t.Errorf("kind/found: got %q/%v", ws.Kind, ws.Found)
	}
	if ws.Generation != 7 || ws.ObservedGeneration != 7 {
		t.Errorf("generation: got %d/%d, want 7/7", ws.Generation, ws.ObservedGeneration)
	}
	if ws.SpecReplicas != 1 || ws.Replicas != 1 || ws.UpdatedReplicas != 1 || ws.ReadyReplicas != 1 || ws.AvailableReplicas != 1 {
		t.Errorf("replica counts mismatch: %+v", ws)
	}
	if len(ws.Conditions) != 2 {
		t.Fatalf("conditions: got %d, want 2", len(ws.Conditions))
	}
	if ws.Conditions[0].Type != "Available" || ws.Conditions[0].Status != "True" || ws.Conditions[0].Reason != "MinimumReplicasAvailable" {
		t.Errorf("available condition: %+v", ws.Conditions[0])
	}
	if ws.Conditions[1].Type != "Progressing" || ws.Conditions[1].Status != "True" {
		t.Errorf("progressing condition: %+v", ws.Conditions[1])
	}
}

func TestRolloutStatus_StatefulSet(t *testing.T) {
	ss := &appsv1.StatefulSet{
		ObjectMeta: metav1.ObjectMeta{Name: "db", Namespace: "default", Generation: 2},
		Spec:       appsv1.StatefulSetSpec{Replicas: int32Ptr(3)},
		Status: appsv1.StatefulSetStatus{
			ObservedGeneration: 2,
			Replicas:           3,
			UpdatedReplicas:    3,
			ReadyReplicas:      3,
			AvailableReplicas:  3,
		},
	}
	c := &realK8sClient{cs: kubefake.NewSimpleClientset(ss)}

	out, err := c.RolloutStatus(context.Background(), "default", "db")
	if err != nil {
		t.Fatalf("RolloutStatus: %v", err)
	}
	var ws workloadStatus
	if err := json.Unmarshal([]byte(out), &ws); err != nil {
		t.Fatalf("unmarshal: %v; raw=%s", err, out)
	}
	if ws.Kind != "StatefulSet" || !ws.Found {
		t.Errorf("kind/found: got %q/%v", ws.Kind, ws.Found)
	}
	if ws.Conditions == nil || len(ws.Conditions) != 0 {
		t.Errorf("statefulset conditions should serialize as empty array, got %+v", ws.Conditions)
	}
}

func TestRolloutStatus_NotFound(t *testing.T) {
	c := &realK8sClient{cs: kubefake.NewSimpleClientset()}

	out, err := c.RolloutStatus(context.Background(), "default", "missing")
	if err != nil {
		t.Fatalf("RolloutStatus should not error on not-found: %v", err)
	}
	var ws workloadStatus
	if err := json.Unmarshal([]byte(out), &ws); err != nil {
		t.Fatalf("unmarshal: %v; raw=%s", err, out)
	}
	if ws.Found {
		t.Errorf("expected found=false, got %+v", ws)
	}
	if ws.Conditions == nil || len(ws.Conditions) != 0 {
		t.Errorf("expected empty conditions array, got %+v", ws.Conditions)
	}
}
