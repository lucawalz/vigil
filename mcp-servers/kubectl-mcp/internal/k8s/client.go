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

const eventsDelimiter = "\nEvents:"

type K8sClient interface {
	GetNodes(ctx context.Context) (string, error)
	GetPods(ctx context.Context, namespace string) (string, error)
	DescribePod(ctx context.Context, namespace, name string) (string, error)
	GetLogs(ctx context.Context, namespace, name, container string, tailLines int64) (string, error)
	RolloutStatus(ctx context.Context, namespace, deploymentName string) (string, error)
	GetEvents(ctx context.Context, namespace, fieldSelector string) (string, error)
	DescribeNode(ctx context.Context, name string) (string, error)
	GetTaints(ctx context.Context, node string) (string, error)
	DeleteResource(ctx context.Context, kind, namespace, name string) (string, error)
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
	prefix, events, err := c.describePodWithSplit(ctx, namespace, name)
	if err != nil {
		return "", err
	}
	return prefix + events, nil
}

func (c *realK8sClient) describePodWithSplit(ctx context.Context, namespace, name string) (prefix, events string, err error) {
	pod, err := c.cs.CoreV1().Pods(namespace).Get(ctx, name, metav1.GetOptions{})
	if err != nil {
		return "", "", fmt.Errorf("get pod: %w", err)
	}
	var sb strings.Builder
	fmt.Fprintf(&sb, "Name:      %s\n", pod.Name)
	fmt.Fprintf(&sb, "Namespace: %s\n", pod.Namespace)
	fmt.Fprintf(&sb, "Node:      %s\n", pod.Spec.NodeName)
	fmt.Fprintf(&sb, "Status:    %s\n", string(pod.Status.Phase))
	fmt.Fprintf(&sb, "IP:        %s\n", pod.Status.PodIP)
	sb.WriteString("Containers:\n")
	for _, ct := range pod.Spec.Containers {
		fmt.Fprintf(&sb, "  %s:\n    Image: %s\n", ct.Name, ct.Image)
	}
	if len(pod.Status.ContainerStatuses) > 0 {
		sb.WriteString("ContainerStatuses:\n")
		for _, cs := range pod.Status.ContainerStatuses {
			fmt.Fprintf(&sb, "  %s: Ready=%v RestartCount=%d\n",
				cs.Name, cs.Ready, cs.RestartCount)
		}
	}
	fs := fmt.Sprintf("involvedObject.name=%s,involvedObject.namespace=%s", name, namespace)
	evList, evErr := c.cs.CoreV1().Events(namespace).List(ctx, metav1.ListOptions{FieldSelector: fs})
	if evErr != nil {
		return sb.String(), "", fmt.Errorf("list events: %w", evErr)
	}
	var evb strings.Builder
	evb.WriteString(eventsDelimiter + "\n")
	for _, ev := range evList.Items {
		age := fmt.Sprintf("%.0fs", time.Since(ev.LastTimestamp.Time).Seconds())
		fmt.Fprintf(&evb, "  %-5s  %-8s  %-20s  %s\n", age, ev.Type, ev.Reason, ev.Message)
	}
	return sb.String(), evb.String(), nil
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

func (c *realK8sClient) GetEvents(ctx context.Context, namespace, fieldSelector string) (string, error) {
	list, err := c.cs.CoreV1().Events(namespace).List(ctx, metav1.ListOptions{FieldSelector: fieldSelector})
	if err != nil {
		return "", fmt.Errorf("list events: %w", err)
	}
	var sb strings.Builder
	sb.WriteString("TYPE\tREASON\tOBJECT\tMESSAGE\tAGE\n")
	for _, ev := range list.Items {
		age := fmt.Sprintf("%.0fs", time.Since(ev.LastTimestamp.Time).Seconds())
		obj := fmt.Sprintf("%s/%s", ev.InvolvedObject.Kind, ev.InvolvedObject.Name)
		fmt.Fprintf(&sb, "%s\t%s\t%s\t%s\t%s\n", ev.Type, ev.Reason, obj, ev.Message, age)
	}
	return sb.String(), nil
}

func (c *realK8sClient) DescribeNode(ctx context.Context, name string) (string, error) {
	node, err := c.cs.CoreV1().Nodes().Get(ctx, name, metav1.GetOptions{})
	if err != nil {
		return "", fmt.Errorf("get node: %w", err)
	}
	var sb strings.Builder
	fmt.Fprintf(&sb, "Name: %s\n", node.Name)
	sb.WriteString("Labels:\n")
	for k, v := range node.Labels {
		fmt.Fprintf(&sb, "  %s=%s\n", k, v)
	}
	sb.WriteString("Taints:\n")
	if len(node.Spec.Taints) == 0 {
		sb.WriteString("  <none>\n")
	}
	for _, t := range node.Spec.Taints {
		fmt.Fprintf(&sb, "  %s=%s:%s\n", t.Key, t.Value, string(t.Effect))
	}
	sb.WriteString("Conditions:\n")
	for _, cond := range node.Status.Conditions {
		fmt.Fprintf(&sb, "  %s: %s\n", string(cond.Type), string(cond.Status))
	}
	sb.WriteString("Capacity:\n")
	for res, qty := range node.Status.Capacity {
		fmt.Fprintf(&sb, "  %s: %s\n", string(res), qty.String())
	}
	sb.WriteString("Allocatable:\n")
	for res, qty := range node.Status.Allocatable {
		fmt.Fprintf(&sb, "  %s: %s\n", string(res), qty.String())
	}
	fmt.Fprintf(&sb, "KubeletVersion: %s\n", node.Status.NodeInfo.KubeletVersion)
	return sb.String(), nil
}

func (c *realK8sClient) GetTaints(ctx context.Context, node string) (string, error) {
	n, err := c.cs.CoreV1().Nodes().Get(ctx, node, metav1.GetOptions{})
	if err != nil {
		return "", fmt.Errorf("get node: %w", err)
	}
	if len(n.Spec.Taints) == 0 {
		return fmt.Sprintf("Node %s has no taints\n", node), nil
	}
	var sb strings.Builder
	fmt.Fprintf(&sb, "Taints on %s:\n", node)
	for _, t := range n.Spec.Taints {
		fmt.Fprintf(&sb, "  %s=%s:%s\n", t.Key, t.Value, string(t.Effect))
	}
	return sb.String(), nil
}

func (c *realK8sClient) DeleteResource(ctx context.Context, kind, namespace, name string) (string, error) {
	policy := metav1.DeletePropagationForeground
	opts := metav1.DeleteOptions{PropagationPolicy: &policy}
	var err error
	switch kind {
	case "Deployment":
		err = c.cs.AppsV1().Deployments(namespace).Delete(ctx, name, opts)
	case "StatefulSet":
		err = c.cs.AppsV1().StatefulSets(namespace).Delete(ctx, name, opts)
	case "Pod":
		err = c.cs.CoreV1().Pods(namespace).Delete(ctx, name, opts)
	case "ConfigMap":
		err = c.cs.CoreV1().ConfigMaps(namespace).Delete(ctx, name, opts)
	case "Service":
		err = c.cs.CoreV1().Services(namespace).Delete(ctx, name, opts)
	case "PersistentVolumeClaim":
		err = c.cs.CoreV1().PersistentVolumeClaims(namespace).Delete(ctx, name, opts)
	case "ResourceQuota":
		err = c.cs.CoreV1().ResourceQuotas(namespace).Delete(ctx, name, opts)
	case "NetworkPolicy":
		err = c.cs.NetworkingV1().NetworkPolicies(namespace).Delete(ctx, name, opts)
	default:
		return fmt.Sprintf("unsupported kind: %s", kind), nil
	}
	if err != nil {
		return "", fmt.Errorf("delete %s/%s/%s: %w", kind, namespace, name, err)
	}
	return fmt.Sprintf("%s/%s/%s deleted", kind, namespace, name), nil
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
