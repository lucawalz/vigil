package k8s

import (
	"context"
	"fmt"
	"io"
	"log"
	"strings"
	"time"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/types"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
)

// K8sClient is the interface handlers depend on. The real implementation uses
// client-go; tests inject a fake struct. The Go compiler enforces that
// internal/ packages can only be used within this module.
type K8sClient interface {
	GetPods(ctx context.Context, namespace string) (string, error)
	DescribePod(ctx context.Context, namespace, name string) (string, error)
	GetLogs(ctx context.Context, namespace, name, container string, tailLines int64) (string, error)
	RolloutUndo(ctx context.Context, namespace, deploymentName string) (string, error)
	ApplyPatch(ctx context.Context, namespace, resourceType, name, patch string) (string, error)
	RolloutStatus(ctx context.Context, namespace, deploymentName string) (string, error)
}

type realK8sClient struct {
	cs *kubernetes.Clientset
}

// NewRealK8sClient creates one singleton Clientset at server startup.
// Never create a new clientset per tool call — TCP+TLS handshake is expensive.
func NewRealK8sClient(cfg *rest.Config) K8sClient {
	cs, err := kubernetes.NewForConfig(cfg)
	if err != nil {
		log.Fatalf("kubernetes.NewForConfig: %v", err)
	}
	return &realK8sClient{cs: cs}
}

func (c *realK8sClient) GetPods(ctx context.Context, namespace string) (string, error) {
	list, err := c.cs.CoreV1().Pods(namespace).List(ctx, metav1.ListOptions{})
	if err != nil {
		return "", fmt.Errorf("list pods: %w", err)
	}
	var sb strings.Builder
	sb.WriteString("NAMESPACE\tNAME\tSTATUS\tREADY\n")
	for _, pod := range list.Items {
		ready := 0
		total := len(pod.Spec.Containers)
		for _, cs := range pod.Status.ContainerStatuses {
			if cs.Ready {
				ready++
			}
		}
		fmt.Fprintf(&sb, "%s\t%s\t%s\t%d/%d\n",
			pod.Namespace, pod.Name, string(pod.Status.Phase), ready, total)
	}
	return sb.String(), nil
}

func (c *realK8sClient) DescribePod(ctx context.Context, namespace, name string) (string, error) {
	pod, err := c.cs.CoreV1().Pods(namespace).Get(ctx, name, metav1.GetOptions{})
	if err != nil {
		return "", fmt.Errorf("get pod: %w", err)
	}
	var sb strings.Builder
	fmt.Fprintf(&sb, "Name:      %s\n", pod.Name)
	fmt.Fprintf(&sb, "Namespace: %s\n", pod.Namespace)
	fmt.Fprintf(&sb, "Node:      %s\n", pod.Spec.NodeName)
	fmt.Fprintf(&sb, "Status:    %s\n", string(pod.Status.Phase))
	fmt.Fprintf(&sb, "IP:        %s\n", pod.Status.PodIP)
	sb.WriteString("Containers:\n")
	for _, c := range pod.Spec.Containers {
		fmt.Fprintf(&sb, "  %s:\n    Image: %s\n", c.Name, c.Image)
	}
	if len(pod.Status.ContainerStatuses) > 0 {
		sb.WriteString("ContainerStatuses:\n")
		for _, cs := range pod.Status.ContainerStatuses {
			fmt.Fprintf(&sb, "  %s: Ready=%v RestartCount=%d\n",
				cs.Name, cs.Ready, cs.RestartCount)
		}
	}
	return sb.String(), nil
}

func (c *realK8sClient) GetLogs(ctx context.Context, namespace, name, container string, tailLines int64) (string, error) {
	opts := &corev1.PodLogOptions{
		Container: container,
		TailLines: &tailLines,
	}
	stream, err := c.cs.CoreV1().Pods(namespace).GetLogs(name, opts).Stream(ctx)
	if err != nil {
		return "", fmt.Errorf("get logs: %w", err)
	}
	defer func() { _ = stream.Close() }()
	data, err := io.ReadAll(stream)
	if err != nil {
		return "", fmt.Errorf("read logs: %w", err)
	}
	return string(data), nil
}

func (c *realK8sClient) RolloutUndo(ctx context.Context, namespace, deploymentName string) (string, error) {
	// Trigger a rolling restart by setting restartedAt to the current time.
	// This causes the deployment controller to replace all pods one by one.
	patch := fmt.Sprintf(
		`{"spec":{"template":{"metadata":{"annotations":{"kubectl.kubernetes.io/restartedAt":%q}}}}}`,
		time.Now().UTC().Format(time.RFC3339),
	)
	_, err := c.cs.AppsV1().Deployments(namespace).Patch(
		ctx, deploymentName, types.MergePatchType, []byte(patch), metav1.PatchOptions{},
	)
	if err != nil {
		return "", fmt.Errorf("rollout undo patch: %w", err)
	}
	return fmt.Sprintf("deployment.apps/%s restarted", deploymentName), nil
}

func (c *realK8sClient) ApplyPatch(ctx context.Context, namespace, resourceType, name, patch string) (string, error) {
	var result string
	switch resourceType {
	case "deployment", "deployments":
		dep, err := c.cs.AppsV1().Deployments(namespace).Patch(
			ctx, name, types.MergePatchType, []byte(patch), metav1.PatchOptions{},
		)
		if err != nil {
			return "", fmt.Errorf("patch deployment: %w", err)
		}
		result = fmt.Sprintf("deployment.apps/%s patched", dep.Name)
	case "statefulset", "statefulsets":
		ss, err := c.cs.AppsV1().StatefulSets(namespace).Patch(
			ctx, name, types.MergePatchType, []byte(patch), metav1.PatchOptions{},
		)
		if err != nil {
			return "", fmt.Errorf("patch statefulset: %w", err)
		}
		result = fmt.Sprintf("statefulset.apps/%s patched", ss.Name)
	default:
		return "", fmt.Errorf("unsupported resource type: %s (supported: deployment, statefulset)", resourceType)
	}
	return result, nil
}

func (c *realK8sClient) RolloutStatus(ctx context.Context, namespace, deploymentName string) (string, error) {
	dep, err := c.cs.AppsV1().Deployments(namespace).Get(ctx, deploymentName, metav1.GetOptions{})
	if err != nil {
		return "", fmt.Errorf("get deployment: %w", err)
	}
	desired := dep.Spec.Replicas
	desiredCount := int32(0)
	if desired != nil {
		desiredCount = *desired
	}
	updated := dep.Status.UpdatedReplicas
	ready := dep.Status.ReadyReplicas
	available := dep.Status.AvailableReplicas
	var sb strings.Builder
	sb.WriteString(fmt.Sprintf("Deployment: %s/%s\n", namespace, deploymentName))
	sb.WriteString(fmt.Sprintf("Desired:    %d\n", desiredCount))
	sb.WriteString(fmt.Sprintf("Updated:    %d\n", updated))
	sb.WriteString(fmt.Sprintf("Ready:      %d\n", ready))
	sb.WriteString(fmt.Sprintf("Available:  %d\n", available))
	if ready == desiredCount && updated == desiredCount {
		sb.WriteString("Status:     Rolled out successfully\n")
	} else {
		sb.WriteString("Status:     Rolling out...\n")
	}
	return sb.String(), nil
}
