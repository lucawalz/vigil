package flux

import (
	"context"
	"encoding/json"
	"fmt"
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

var gitRepositoryGVR = schema.GroupVersionResource{
	Group:    "source.toolkit.fluxcd.io",
	Version:  "v1",
	Resource: "gitrepositories",
}

type FluxClient interface {
	ReconcileKustomization(ctx context.Context, namespace, name string) (string, error)
	GetKustomizationStatus(ctx context.Context, namespace, name string) (string, error)
	GetGitRepositoryStatus(ctx context.Context, namespace, name string) (string, error)
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

type fluxStatusJSON struct {
	Kind      string `json:"kind"`
	Namespace string `json:"namespace"`
	Name      string `json:"name"`
	Found     bool   `json:"found"`
	Ready     *bool  `json:"ready"`
	Reason    string `json:"reason"`
	Message   string `json:"message"`
	Revision  string `json:"revision"`
	Suspended bool   `json:"suspended"`
}

func readyCondition(status map[string]interface{}) (*bool, string, string) {
	conditions, ok := status["conditions"].([]interface{})
	if !ok {
		return nil, "", ""
	}
	for _, c := range conditions {
		cond, ok := c.(map[string]interface{})
		if !ok {
			continue
		}
		if condType, _ := cond["type"].(string); condType == "Ready" {
			condStatus, _ := cond["status"].(string)
			reason, _ := cond["reason"].(string)
			message, _ := cond["message"].(string)
			ready := condStatus == "True"
			return &ready, reason, message
		}
	}
	return nil, "", ""
}

func marshalFluxStatus(s fluxStatusJSON) (string, error) {
	out, err := json.Marshal(s)
	if err != nil {
		return "", fmt.Errorf("marshal flux status: %w", err)
	}
	return string(out), nil
}

func (c *realFluxClient) GetKustomizationStatus(ctx context.Context, namespace, name string) (string, error) {
	obj, err := c.dynClient.Resource(kustomizationGVR).Namespace(namespace).Get(
		ctx, name, metav1.GetOptions{},
	)
	if err != nil {
		return "", fmt.Errorf("get kustomization %s/%s: %w", namespace, name, err)
	}

	out := fluxStatusJSON{Kind: "Kustomization", Namespace: namespace, Name: name, Found: true}
	if spec, ok := obj.Object["spec"].(map[string]interface{}); ok {
		out.Suspended, _ = spec["suspend"].(bool)
	}
	if status, ok := obj.Object["status"].(map[string]interface{}); ok {
		out.Ready, out.Reason, out.Message = readyCondition(status)
		out.Revision, _ = status["lastAppliedRevision"].(string)
	}
	return marshalFluxStatus(out)
}

func (c *realFluxClient) GetGitRepositoryStatus(ctx context.Context, namespace, name string) (string, error) {
	obj, err := c.dynClient.Resource(gitRepositoryGVR).Namespace(namespace).Get(
		ctx, name, metav1.GetOptions{},
	)
	if err != nil {
		return "", fmt.Errorf("get gitrepository %s/%s: %w", namespace, name, err)
	}

	out := fluxStatusJSON{Kind: "GitRepository", Namespace: namespace, Name: name, Found: true}
	if status, ok := obj.Object["status"].(map[string]interface{}); ok {
		out.Ready, out.Reason, out.Message = readyCondition(status)
		if artifact, ok := status["artifact"].(map[string]interface{}); ok {
			out.Revision, _ = artifact["revision"].(string)
		}
	}
	return marshalFluxStatus(out)
}
