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
	pods          string
	describePod   string
	logs          string
	rolloutStatus string
	err           error
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

func TestKubectlToolInventory(t *testing.T) {
	fake := &fakeK8sClient{}
	cfg := &config.Config{MaxOutputBytesDescribe: 4096, MaxOutputBytesLogs: 4096}
	mcpSrv := kubectlserver.NewServer(fake, cfg)

	tools := mcpSrv.ListTools()
	names := make(map[string]bool, len(tools))
	for _, tool := range tools {
		names[tool.Tool.Name] = true
	}

	required := []string{"get_nodes", "get_pods", "describe_pod", "get_logs", "rollout_status"}
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
	if len(tools) != 5 {
		t.Errorf("expected exactly 5 tools, got %d", len(tools))
	}
}
