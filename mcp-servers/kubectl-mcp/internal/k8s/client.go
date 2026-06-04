package k8s

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"strings"
	"time"

	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	k8serrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/api/meta"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"k8s.io/client-go/discovery/cached/memory"
	"k8s.io/client-go/dynamic"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
	"k8s.io/client-go/restmapper"
	sigsyaml "sigs.k8s.io/yaml"
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
	GetResourceYAML(ctx context.Context, kind, namespace, name string) (string, error)
}

type realK8sClient struct {
	cs kubernetes.Interface
	dc dynamic.Interface
	rm meta.RESTMapper
}

func NewRealK8sClient(cfg *rest.Config) K8sClient {
	cs, err := kubernetes.NewForConfig(cfg)
	if err != nil {
		log.Fatalf("kubernetes.NewForConfig: %v", err)
	}
	dc, err := dynamic.NewForConfig(cfg)
	if err != nil {
		log.Fatalf("dynamic.NewForConfig: %v", err)
	}
	cached := memory.NewMemCacheClient(cs.Discovery())
	rm := restmapper.NewDeferredDiscoveryRESTMapper(cached)
	return &realK8sClient{cs: cs, dc: dc, rm: rm}
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

func (c *realK8sClient) GetResourceYAML(ctx context.Context, kind, namespace, name string) (string, error) {
	gvk, err := c.resolveKind(kind)
	if err != nil {
		return "", err
	}
	mapping, err := c.rm.RESTMapping(gvk.GroupKind(), gvk.Version)
	if err != nil {
		return "", fmt.Errorf("map kind %s: %w", kind, err)
	}
	var obj *unstructured.Unstructured
	if mapping.Scope.Name() == meta.RESTScopeNameRoot {
		obj, err = c.dc.Resource(mapping.Resource).Get(ctx, name, metav1.GetOptions{})
	} else {
		obj, err = c.dc.Resource(mapping.Resource).Namespace(namespace).Get(ctx, name, metav1.GetOptions{})
	}
	if err != nil {
		return "", fmt.Errorf("get %s/%s/%s: %w", kind, namespace, name, err)
	}
	unstructured.RemoveNestedField(obj.Object, "metadata", "managedFields")
	unstructured.RemoveNestedField(obj.Object, "metadata", "resourceVersion")
	unstructured.RemoveNestedField(obj.Object, "metadata", "uid")
	unstructured.RemoveNestedField(obj.Object, "metadata", "generation")
	unstructured.RemoveNestedField(obj.Object, "metadata", "creationTimestamp")
	unstructured.RemoveNestedField(obj.Object, "status")
	out, err := sigsyaml.Marshal(obj.Object)
	if err != nil {
		return "", fmt.Errorf("marshal yaml: %w", err)
	}
	return string(out), nil
}

func (c *realK8sClient) resolveKind(kind string) (schema.GroupVersionKind, error) {
	_, lists, err := c.cs.Discovery().ServerGroupsAndResources()
	if lists == nil {
		return schema.GroupVersionKind{}, fmt.Errorf("discovery: %w", err)
	}
	for _, list := range lists {
		gv, parseErr := schema.ParseGroupVersion(list.GroupVersion)
		if parseErr != nil {
			continue
		}
		for _, r := range list.APIResources {
			if r.Kind == kind {
				return gv.WithKind(kind), nil
			}
		}
	}
	return schema.GroupVersionKind{}, fmt.Errorf("kind %q not found in discovery", kind)
}

type workloadCondition struct {
	Type   string `json:"type"`
	Status string `json:"status"`
	Reason string `json:"reason"`
}

type workloadStatus struct {
	Kind               string              `json:"kind"`
	Namespace          string              `json:"namespace"`
	Name               string              `json:"name"`
	Found              bool                `json:"found"`
	Generation         int64               `json:"generation"`
	ObservedGeneration int64               `json:"observedGeneration"`
	SpecReplicas       int32               `json:"specReplicas"`
	Replicas           int32               `json:"replicas"`
	UpdatedReplicas    int32               `json:"updatedReplicas"`
	ReadyReplicas      int32               `json:"readyReplicas"`
	AvailableReplicas  int32               `json:"availableReplicas"`
	Conditions         []workloadCondition `json:"conditions"`
}

func specReplicaCount(replicas *int32) int32 {
	if replicas == nil {
		return 0
	}
	return *replicas
}

func marshalWorkloadStatus(ws workloadStatus) (string, error) {
	out, err := json.Marshal(ws)
	if err != nil {
		return "", fmt.Errorf("marshal workload status: %w", err)
	}
	return string(out), nil
}

func (c *realK8sClient) RolloutStatus(ctx context.Context, namespace, name string) (string, error) {
	dep, err := c.cs.AppsV1().Deployments(namespace).Get(ctx, name, metav1.GetOptions{})
	if err != nil && !k8serrors.IsNotFound(err) {
		return "", fmt.Errorf("get deployment: %w", err)
	}
	if err == nil {
		return marshalWorkloadStatus(deploymentWorkloadStatus(namespace, name, dep))
	}
	ss, ssErr := c.cs.AppsV1().StatefulSets(namespace).Get(ctx, name, metav1.GetOptions{})
	if ssErr != nil && !k8serrors.IsNotFound(ssErr) {
		return "", fmt.Errorf("get statefulset: %w", ssErr)
	}
	if ssErr == nil {
		return marshalWorkloadStatus(statefulSetWorkloadStatus(namespace, name, ss))
	}
	return marshalWorkloadStatus(workloadStatus{
		Namespace:  namespace,
		Name:       name,
		Found:      false,
		Conditions: []workloadCondition{},
	})
}

func deploymentWorkloadStatus(namespace, name string, dep *appsv1.Deployment) workloadStatus {
	conditions := make([]workloadCondition, 0, len(dep.Status.Conditions))
	for _, cond := range dep.Status.Conditions {
		conditions = append(conditions, workloadCondition{
			Type:   string(cond.Type),
			Status: string(cond.Status),
			Reason: cond.Reason,
		})
	}
	return workloadStatus{
		Kind:               "Deployment",
		Namespace:          namespace,
		Name:               name,
		Found:              true,
		Generation:         dep.Generation,
		ObservedGeneration: dep.Status.ObservedGeneration,
		SpecReplicas:       specReplicaCount(dep.Spec.Replicas),
		Replicas:           dep.Status.Replicas,
		UpdatedReplicas:    dep.Status.UpdatedReplicas,
		ReadyReplicas:      dep.Status.ReadyReplicas,
		AvailableReplicas:  dep.Status.AvailableReplicas,
		Conditions:         conditions,
	}
}

func statefulSetWorkloadStatus(namespace, name string, ss *appsv1.StatefulSet) workloadStatus {
	return workloadStatus{
		Kind:               "StatefulSet",
		Namespace:          namespace,
		Name:               name,
		Found:              true,
		Generation:         ss.Generation,
		ObservedGeneration: ss.Status.ObservedGeneration,
		SpecReplicas:       specReplicaCount(ss.Spec.Replicas),
		Replicas:           ss.Status.Replicas,
		UpdatedReplicas:    ss.Status.UpdatedReplicas,
		ReadyReplicas:      ss.Status.ReadyReplicas,
		AvailableReplicas:  ss.Status.AvailableReplicas,
		Conditions:         []workloadCondition{},
	}
}
