package k8s

import (
	"context"
	"fmt"
	"io"
	"log"
	"strings"
	"time"

	corev1 "k8s.io/api/core/v1"
	k8serrors "k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
)

type K8sClient interface {
	GetNodes(ctx context.Context) (string, error)
	GetPods(ctx context.Context, namespace string) (string, error)
	DescribePod(ctx context.Context, namespace, name string) (string, error)
	GetLogs(ctx context.Context, namespace, name, container string, tailLines int64) (string, error)
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

func (c *realK8sClient) GetNodes(ctx context.Context) (string, error) {
	list, err := c.cs.CoreV1().Nodes().List(ctx, metav1.ListOptions{})
	if err != nil {
		return "", fmt.Errorf("list nodes: %w", err)
	}
	var sb strings.Builder
	sb.WriteString("NAME\tSTATUS\tROLES\tAGE\n")
	for _, node := range list.Items {
		status := "NotReady"
		for _, cond := range node.Status.Conditions {
			if cond.Type == corev1.NodeReady && cond.Status == corev1.ConditionTrue {
				status = "Ready"
			}
		}
		roles := "<none>"
		for label := range node.Labels {
			if label == "node-role.kubernetes.io/master" || label == "node-role.kubernetes.io/control-plane" {
				roles = "control-plane"
			}
		}
		age := fmt.Sprintf("%.0fm", time.Since(node.CreationTimestamp.Time).Minutes())
		fmt.Fprintf(&sb, "%s\t%s\t%s\t%s\n", node.Name, status, roles, age)
	}
	return sb.String(), nil
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

func (c *realK8sClient) RolloutStatus(ctx context.Context, namespace, deploymentName string) (string, error) {
	dep, err := c.cs.AppsV1().Deployments(namespace).Get(ctx, deploymentName, metav1.GetOptions{})
	if err != nil && !k8serrors.IsNotFound(err) {
		return "", fmt.Errorf("get deployment: %w", err)
	}
	if err == nil {
		desired := dep.Spec.Replicas
		desiredCount := int32(0)
		if desired != nil {
			desiredCount = *desired
		}
		updated := dep.Status.UpdatedReplicas
		ready := dep.Status.ReadyReplicas
		available := dep.Status.AvailableReplicas
		var sb strings.Builder
		fmt.Fprintf(&sb, "Deployment: %s/%s\n", namespace, deploymentName)
		fmt.Fprintf(&sb, "Desired:    %d\n", desiredCount)
		fmt.Fprintf(&sb, "Updated:    %d\n", updated)
		fmt.Fprintf(&sb, "Ready:      %d\n", ready)
		fmt.Fprintf(&sb, "Available:  %d\n", available)
		if ready == desiredCount && updated == desiredCount {
			sb.WriteString("Status:     Rolled out successfully\n")
		} else {
			sb.WriteString("Status:     Rolling out...\n")
		}
		return sb.String(), nil
	}
	ss, ssErr := c.cs.AppsV1().StatefulSets(namespace).Get(ctx, deploymentName, metav1.GetOptions{})
	if ssErr != nil {
		return "", fmt.Errorf("%s not found as deployment or statefulset in namespace %s", deploymentName, namespace)
	}
	desired := ss.Spec.Replicas
	desiredCount := int32(0)
	if desired != nil {
		desiredCount = *desired
	}
	ready := ss.Status.ReadyReplicas
	updated := ss.Status.UpdatedReplicas
	var sb strings.Builder
	fmt.Fprintf(&sb, "StatefulSet: %s/%s\n", namespace, deploymentName)
	fmt.Fprintf(&sb, "Desired:     %d\n", desiredCount)
	fmt.Fprintf(&sb, "Updated:     %d\n", updated)
	fmt.Fprintf(&sb, "Ready:       %d\n", ready)
	if ready == desiredCount && updated == desiredCount {
		sb.WriteString("Status:      Rolled out successfully\n")
	} else {
		sb.WriteString("Status:      Rolling out...\n")
	}
	return sb.String(), nil
}
