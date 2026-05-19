package k8s_test

import (
	"context"
	"fmt"
	"strings"
	"testing"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/mcptest"
	"github.com/mark3labs/mcp-go/server"

	"github.com/lucawalz/vigil/mcp-servers/kubectl-mcp/internal/config"
	"github.com/lucawalz/vigil/mcp-servers/kubectl-mcp/internal/k8s"
	kubectlserver "github.com/lucawalz/vigil/mcp-servers/kubectl-mcp/internal/server"
)

type fakeK8sClient struct {
	pods            string
	describePod     string
	logs            string
	rolloutStatus   string
	events          string
	describeNode    string
	taints          string
	deleteResource  string
	getResourceYAML string
	err             error
}

var _ k8s.K8sClient = &fakeK8sClient{}

func (f *fakeK8sClient) GetPods(_ context.Context, _ string) (string, error) {
	return f.pods, f.err
}

func (f *fakeK8sClient) DescribePod(_ context.Context, _, _ string) (string, error) {
	return f.describePod, f.err
}

func (f *fakeK8sClient) GetLogs(_ context.Context, _, _, _ string, _ int64) (string, error) {
	return f.logs, f.err
}

func (f *fakeK8sClient) GetNodes(_ context.Context) (string, error) {
	return "", f.err
}

func (f *fakeK8sClient) RolloutStatus(_ context.Context, _, _ string) (string, error) {
	return f.rolloutStatus, f.err
}

func (f *fakeK8sClient) GetEvents(_ context.Context, _, _ string) (string, error) {
	return f.events, f.err
}

func (f *fakeK8sClient) DescribeNode(_ context.Context, _ string) (string, error) {
	return f.describeNode, f.err
}

func (f *fakeK8sClient) GetTaints(_ context.Context, _ string) (string, error) {
	return f.taints, f.err
}

func (f *fakeK8sClient) DeleteResource(_ context.Context, _, _, _ string) (string, error) {
	return f.deleteResource, f.err
}

func (f *fakeK8sClient) GetResourceYAML(_ context.Context, _, _, _ string) (string, error) {
	return f.getResourceYAML, f.err
}

func callGetPods(t *testing.T, fake *fakeK8sClient, maxBytes int, args map[string]any) (*mcp.CallToolResult, error) {
	t.Helper()
	srv, err := mcptest.NewServer(t, server.ServerTool{
		Tool: mcp.NewTool("get_pods",
			mcp.WithString("namespace", mcp.Required()),
		),
		Handler: k8s.HandleGetPods(fake, maxBytes),
	})
	if err != nil {
		return nil, err
	}
	defer srv.Close()

	var req mcp.CallToolRequest
	req.Params.Name = "get_pods"
	req.Params.Arguments = args
	return srv.Client().CallTool(context.Background(), req)
}

func TestGetPodsHandler_Success(t *testing.T) {
	fake := &fakeK8sClient{pods: "pod-1 Running\npod-2 Running\n"}
	result, err := callGetPods(t, fake, 4096, map[string]any{"namespace": "default"})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success, got error result")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "pod-1") {
		t.Errorf("expected pod-1 in response, got: %s", text)
	}
}

func TestGetPodsHandler_Truncation(t *testing.T) {
	fake := &fakeK8sClient{pods: strings.Repeat("pod-line\n", 1000)}
	result, err := callGetPods(t, fake, 4096, map[string]any{"namespace": "default"})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success, got error result")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "[TRUNCATED:") {
		t.Errorf("expected truncation marker, got: %.100s", text)
	}
}

func TestGetPodsHandler_DomainError(t *testing.T) {
	fake := &fakeK8sClient{err: fmt.Errorf("connection refused")}
	result, err := callGetPods(t, fake, 4096, map[string]any{"namespace": "default"})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for domain error")
	}
}

func TestGetPodsHandler_MissingNamespace(t *testing.T) {
	fake := &fakeK8sClient{pods: "some-pod Running\n"}
	result, err := callGetPods(t, fake, 4096, map[string]any{})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for missing namespace")
	}
	if len(result.Content) == 0 {
		t.Fatal("expected error message content")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "namespace") {
		t.Errorf("expected 'namespace' in error message, got: %s", text)
	}
}

func TestDescribePodHandler_Success(t *testing.T) {
	fake := &fakeK8sClient{describePod: "Name: my-pod\nNamespace: default\nStatus: Running\n"}
	srv, err := mcptest.NewServer(t, server.ServerTool{
		Tool: mcp.NewTool("describe_pod",
			mcp.WithString("namespace", mcp.Required()),
			mcp.WithString("name", mcp.Required()),
		),
		Handler: k8s.HandleDescribePod(fake, 4096),
	})
	if err != nil {
		t.Fatal(err)
	}
	defer srv.Close()

	var req mcp.CallToolRequest
	req.Params.Name = "describe_pod"
	req.Params.Arguments = map[string]any{"namespace": "default", "name": "my-pod"}
	result, err := srv.Client().CallTool(context.Background(), req)
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success, got error result")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "my-pod") {
		t.Errorf("expected pod name in response, got: %s", text)
	}
}

func TestGetLogsHandler_Success(t *testing.T) {
	fake := &fakeK8sClient{logs: "2026-01-01 INFO server started\n"}
	srv, err := mcptest.NewServer(t, server.ServerTool{
		Tool: mcp.NewTool("get_logs",
			mcp.WithString("namespace", mcp.Required()),
			mcp.WithString("name", mcp.Required()),
			mcp.WithString("container", mcp.Required()),
		),
		Handler: k8s.HandleGetLogs(fake, 2048),
	})
	if err != nil {
		t.Fatal(err)
	}
	defer srv.Close()

	var req mcp.CallToolRequest
	req.Params.Name = "get_logs"
	req.Params.Arguments = map[string]any{
		"namespace": "default", "name": "my-pod", "container": "app",
	}
	result, err := srv.Client().CallTool(context.Background(), req)
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success, got error result")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "server started") {
		t.Errorf("expected log content in response, got: %s", text)
	}
}

func TestRolloutStatusHandler_Success(t *testing.T) {
	fake := &fakeK8sClient{rolloutStatus: "Deployment: default/my-app\nDesired: 3\nReady: 3\n"}
	srv, err := mcptest.NewServer(t, server.ServerTool{
		Tool: mcp.NewTool("rollout_status",
			mcp.WithString("namespace", mcp.Required()),
			mcp.WithString("deployment", mcp.Required()),
		),
		Handler: k8s.HandleRolloutStatus(fake, 4096),
	})
	if err != nil {
		t.Fatal(err)
	}
	defer srv.Close()

	var req mcp.CallToolRequest
	req.Params.Name = "rollout_status"
	req.Params.Arguments = map[string]any{"namespace": "default", "deployment": "my-app"}
	result, err := srv.Client().CallTool(context.Background(), req)
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success, got error result")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "my-app") {
		t.Errorf("expected deployment name in response, got: %s", text)
	}
}

func callGetResourceYaml(t *testing.T, fake *fakeK8sClient, maxBytes int, args map[string]any) (*mcp.CallToolResult, error) {
	t.Helper()
	srv, err := mcptest.NewServer(t, server.ServerTool{
		Tool: mcp.NewTool("get_resource_yaml",
			mcp.WithString("kind", mcp.Required()),
			mcp.WithString("namespace", mcp.Required()),
			mcp.WithString("name", mcp.Required()),
		),
		Handler: k8s.HandleGetResourceYaml(fake, maxBytes),
	})
	if err != nil {
		return nil, err
	}
	defer srv.Close()

	var req mcp.CallToolRequest
	req.Params.Name = "get_resource_yaml"
	req.Params.Arguments = args
	return srv.Client().CallTool(context.Background(), req)
}

func TestGetResourceYamlHandler_Success(t *testing.T) {
	yaml := "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: my-app\n"
	fake := &fakeK8sClient{getResourceYAML: yaml}
	result, err := callGetResourceYaml(t, fake, 4096, map[string]any{
		"kind": "Deployment", "namespace": "default", "name": "my-app",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success, got error result")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, yaml) {
		t.Errorf("expected YAML in response, got: %s", text)
	}
}

func TestGetResourceYamlHandler_MissingKind(t *testing.T) {
	fake := &fakeK8sClient{}
	result, err := callGetResourceYaml(t, fake, 4096, map[string]any{
		"namespace": "default", "name": "my-app",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for missing kind")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "kind") {
		t.Errorf("expected 'kind' in error message, got: %s", text)
	}
}

func TestGetResourceYamlHandler_MissingNamespace(t *testing.T) {
	fake := &fakeK8sClient{}
	result, err := callGetResourceYaml(t, fake, 4096, map[string]any{
		"kind": "Deployment", "name": "my-app",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for missing namespace")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "namespace") {
		t.Errorf("expected 'namespace' in error message, got: %s", text)
	}
}

func TestGetResourceYamlHandler_MissingName(t *testing.T) {
	fake := &fakeK8sClient{}
	result, err := callGetResourceYaml(t, fake, 4096, map[string]any{
		"kind": "Deployment", "namespace": "default",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for missing name")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "name") {
		t.Errorf("expected 'name' in error message, got: %s", text)
	}
}

func TestGetResourceYamlHandler_DomainError(t *testing.T) {
	fake := &fakeK8sClient{err: fmt.Errorf("connection refused")}
	result, err := callGetResourceYaml(t, fake, 4096, map[string]any{
		"kind": "Deployment", "namespace": "default", "name": "my-app",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for domain error")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "GetResourceYAML") {
		t.Errorf("expected 'GetResourceYAML' in error message, got: %s", text)
	}
}

func TestKubectlToolInventory(t *testing.T) {
	fake := &fakeK8sClient{}
	cfg := &config.Config{MaxOutputBytesDescribe: 4096, MaxOutputBytesLogs: 4096}
	mcpSrv := kubectlserver.NewServer(fake, cfg)

	tools := mcpSrv.ListTools()
	names := make(map[string]bool, len(tools))
	for _, tool := range tools {
		names[tool.Tool.Name] = true
	}

	required := []string{
		"get_nodes", "get_pods", "describe_pod", "get_logs", "rollout_status",
		"get_events", "describe_node", "get_taints", "delete_resource",
		"get_resource_yaml",
	}
	for _, name := range required {
		if !names[name] {
			t.Errorf("expected tool %q to be registered", name)
		}
	}
	if names["rollout_undo"] {
		t.Error("rollout_undo must not be registered")
	}
	if names["apply_patch"] {
		t.Error("apply_patch must not be registered")
	}
	if len(tools) != 10 {
		t.Errorf("expected exactly 10 tools, got %d", len(tools))
	}
}

func TestDescribePodEventsPreserved(t *testing.T) {
	const maxBytes = 200

	prefixBody := strings.Repeat("Name: my-pod\nStatus: Running\nContainers: app\n", 10)
	eventsSection := "\nEvents:\n" +
		"  2m   Normal   Scheduled   Pod   Successfully assigned default/my-pod to worker-1\n" +
		"  90s  Warning  BackOff     Pod   Back-off restarting failed container\n" +
		"  30s  Warning  Failed      Pod   Error: ImagePullBackOff\n"
	describeFull := prefixBody + eventsSection

	if len(prefixBody) <= maxBytes {
		t.Fatalf("test setup error: prefixBody (%d bytes) must exceed maxBytes (%d)", len(prefixBody), maxBytes)
	}

	fake := &fakeK8sClient{describePod: describeFull}
	srv, err := mcptest.NewServer(t, server.ServerTool{
		Tool: mcp.NewTool("describe_pod",
			mcp.WithString("namespace", mcp.Required()),
			mcp.WithString("name", mcp.Required()),
		),
		Handler: k8s.HandleDescribePod(fake, maxBytes),
	})
	if err != nil {
		t.Fatal(err)
	}
	defer srv.Close()

	var req mcp.CallToolRequest
	req.Params.Name = "describe_pod"
	req.Params.Arguments = map[string]any{"namespace": "default", "name": "my-pod"}
	result, err := srv.Client().CallTool(context.Background(), req)
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Fatalf("unexpected error result: %v", result.Content)
	}

	text := result.Content[0].(mcp.TextContent).Text

	eventLines := []string{
		"Successfully assigned default/my-pod to worker-1",
		"Back-off restarting failed container",
		"Error: ImagePullBackOff",
	}
	for _, line := range eventLines {
		if !strings.Contains(text, line) {
			t.Errorf("expected event line %q to appear verbatim in result; got:\n%s", line, text)
		}
	}

	if !strings.Contains(text, "[TRUNCATED:") {
		t.Errorf("expected truncation marker in prefix portion; got:\n%s", text)
	}

	if len(text) <= maxBytes {
		t.Errorf("expected total result length > maxBytes (%d), got %d", maxBytes, len(text))
	}
}
