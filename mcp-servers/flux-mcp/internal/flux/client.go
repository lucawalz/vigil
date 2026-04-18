package flux

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"k8s.io/apimachinery/pkg/types"
	"k8s.io/client-go/dynamic"
	"k8s.io/client-go/rest"
)

var kustomizationGVR = schema.GroupVersionResource{
	Group:    "kustomize.toolkit.fluxcd.io",
	Version:  "v1",
	Resource: "kustomizations",
}

// FluxClient is the interface all handler code depends on. Tests inject a fake;
// production uses the dynamic client below. The Go compiler enforces the boundary.
type FluxClient interface {
	SuspendKustomization(ctx context.Context, namespace, name string) error
	ResumeKustomization(ctx context.Context, namespace, name string) error
	ReconcileKustomization(ctx context.Context, namespace, name string) (string, error)
	GetKustomizationStatus(ctx context.Context, namespace, name string) (string, error)
}

type realFluxClient struct {
	dynClient dynamic.Interface
}

func NewRealFluxClient(cfg *rest.Config) (FluxClient, error) {
	dynClient, err := dynamic.NewForConfig(cfg)
	if err != nil {
		return nil, fmt.Errorf("dynamic.NewForConfig: %w", err)
	}
	return &realFluxClient{dynClient: dynClient}, nil
}

func (c *realFluxClient) SuspendKustomization(ctx context.Context, namespace, name string) error {
	patch := []byte(`{"spec":{"suspend":true}}`)
	_, err := c.dynClient.Resource(kustomizationGVR).Namespace(namespace).Patch(
		ctx, name, types.MergePatchType, patch, metav1.PatchOptions{},
	)
	if err != nil {
		return fmt.Errorf("suspend kustomization %s/%s: %w", namespace, name, err)
	}
	return nil
}

func (c *realFluxClient) ResumeKustomization(ctx context.Context, namespace, name string) error {
	patch := []byte(`{"spec":{"suspend":false}}`)
	_, err := c.dynClient.Resource(kustomizationGVR).Namespace(namespace).Patch(
		ctx, name, types.MergePatchType, patch, metav1.PatchOptions{},
	)
	if err != nil {
		return fmt.Errorf("resume kustomization %s/%s: %w", namespace, name, err)
	}
	return nil
}

func (c *realFluxClient) ReconcileKustomization(ctx context.Context, namespace, name string) (string, error) {
	patch, err := json.Marshal(map[string]interface{}{
		"metadata": map[string]interface{}{
			"annotations": map[string]string{
				"reconcile.fluxcd.io/requestedAt": time.Now().UTC().Format(time.RFC3339),
			},
		},
	})
	if err != nil {
		return "", fmt.Errorf("marshal patch: %w", err)
	}
	_, err = c.dynClient.Resource(kustomizationGVR).Namespace(namespace).Patch(
		ctx, name, types.MergePatchType, patch, metav1.PatchOptions{},
	)
	if err != nil {
		return "", fmt.Errorf("reconcile kustomization %s/%s: %w", namespace, name, err)
	}
	return fmt.Sprintf("kustomization %s/%s reconciliation requested", namespace, name), nil
}

func (c *realFluxClient) GetKustomizationStatus(ctx context.Context, namespace, name string) (string, error) {
	obj, err := c.dynClient.Resource(kustomizationGVR).Namespace(namespace).Get(
		ctx, name, metav1.GetOptions{},
	)
	if err != nil {
		return "", fmt.Errorf("get kustomization %s/%s: %w", namespace, name, err)
	}

	var sb strings.Builder
	fmt.Fprintf(&sb, "Kustomization: %s/%s\n", namespace, name)

	spec, _, _ := unstructuredNested(obj.Object, "spec")
	if spec != nil {
		if suspended, ok := spec.(map[string]interface{})["suspend"].(bool); ok {
			fmt.Fprintf(&sb, "Suspended: %v\n", suspended)
		}
	}

	status, _, _ := unstructuredNested(obj.Object, "status")
	if status != nil {
		if conditions, ok := status.(map[string]interface{})["conditions"].([]interface{}); ok {
			sb.WriteString("Conditions:\n")
			for _, c := range conditions {
				if cond, ok := c.(map[string]interface{}); ok {
					condType, _ := cond["type"].(string)
					condStatus, _ := cond["status"].(string)
					condMsg, _ := cond["message"].(string)
					fmt.Fprintf(&sb, "  %s: %s — %s\n", condType, condStatus, condMsg)
				}
			}
		}
	}

	return sb.String(), nil
}

func unstructuredNested(obj map[string]interface{}, key string) (interface{}, bool, error) {
	v, ok := obj[key]
	return v, ok, nil
}
