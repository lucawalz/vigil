package flux_test

import (
	"context"
	"fmt"
	"strings"
	"testing"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/mcptest"
	"github.com/mark3labs/mcp-go/server"

	"github.com/lucawalz/vigil/mcp-servers/flux-mcp/internal/config"
	"github.com/lucawalz/vigil/mcp-servers/flux-mcp/internal/flux"
	fluxserver "github.com/lucawalz/vigil/mcp-servers/flux-mcp/internal/server"
)

type fakeFluxClient struct {
	reconcileResult           string
	reconcileErr              error
	statusResult              string
	statusErr                 error
	gitRepositoryStatusResult string
	gitRepositoryStatusErr    error
}

var _ flux.FluxClient = &fakeFluxClient{}

func (f *fakeFluxClient) ReconcileKustomization(_ context.Context, _, _ string) (string, error) {
	return f.reconcileResult, f.reconcileErr
}
func (f *fakeFluxClient) GetKustomizationStatus(_ context.Context, _, _ string) (string, error) {
	return f.statusResult, f.statusErr
}
func (f *fakeFluxClient) GetGitRepositoryStatus(_ context.Context, _, _ string) (string, error) {
	return f.gitRepositoryStatusResult, f.gitRepositoryStatusErr
}

func buildTestMCPServer(t *testing.T, fake flux.FluxClient) *mcptest.Server {
	t.Helper()
	cfg := &config.Config{MaxOutputBytesDescribe: 4096}
	mcpSrv := fluxserver.NewFluxServer(fake, cfg)

	tools := mcpSrv.ListTools()
	var serverTools []server.ServerTool
	for _, tool := range tools {
		serverTools = append(serverTools, *tool)
	}
	srv, err := mcptest.NewServer(t, serverTools...)
	if err != nil {
		t.Fatalf("mcptest.NewServer: %v", err)
	}
	return srv
}

func callTool(t *testing.T, srv *mcptest.Server, toolName string, args map[string]any) *mcp.CallToolResult {
	t.Helper()
	var req mcp.CallToolRequest
	req.Params.Name = toolName
	req.Params.Arguments = args
	result, err := srv.Client().CallTool(context.Background(), req)
	if err != nil {
		t.Fatalf("CallTool(%s): %v", toolName, err)
	}
	return result
}

func TestGetKustomizationStatus_NoGuard(t *testing.T) {
	fake := &fakeFluxClient{statusResult: "Kustomization: flux-system/infra\nSuspended: true\n"}
	srv := buildTestMCPServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "get_kustomization_status", map[string]any{
		"namespace": "flux-system", "name": "infra",
	})
	if result.IsError {
		t.Errorf("get_kustomization_status should not be guarded, got error: %v", result.Content)
	}
}

func TestReconcileKustomization_NoGuard(t *testing.T) {
	fake := &fakeFluxClient{reconcileResult: "kustomization flux-system/cluster-apps reconciliation requested"}
	srv := buildTestMCPServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "reconcile_kustomization", map[string]any{
		"namespace": "flux-system", "name": "cluster-apps",
	})
	if result.IsError {
		t.Errorf("reconcile_kustomization must succeed without prior suspend, got error: %v", result.Content)
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "reconciliation requested") {
		t.Errorf("expected reconciliation confirmation, got: %s", text)
	}
}

func TestGetGitRepositoryStatus_Success(t *testing.T) {
	fake := &fakeFluxClient{
		gitRepositoryStatusResult: "GitRepository: flux-system/flux-system\nConditions:\n  Ready: True — Applied revision: main/abc1234\n",
	}
	srv := buildTestMCPServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "get_gitrepository_status", map[string]any{
		"namespace": "flux-system", "name": "flux-system",
	})
	if result.IsError {
		t.Errorf("expected success, got error: %v", result.Content)
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "GitRepository: flux-system/flux-system") {
		t.Errorf("expected GitRepository header in response, got: %s", text)
	}
}

func TestGetGitRepositoryStatus_DomainError(t *testing.T) {
	fake := &fakeFluxClient{gitRepositoryStatusErr: fmt.Errorf("not found")}
	srv := buildTestMCPServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "get_gitrepository_status", map[string]any{
		"namespace": "flux-system", "name": "flux-system",
	})
	if !result.IsError {
		t.Error("expected IsError=true for domain error")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "GetGitRepositoryStatus:") {
		t.Errorf("expected handler prefix in error, got: %s", text)
	}
	if !strings.Contains(text, "not found") {
		t.Errorf("expected original error in message, got: %s", text)
	}
}

func TestGetGitRepositoryStatus_MissingArgument(t *testing.T) {
	fake := &fakeFluxClient{}
	srv := buildTestMCPServer(t, fake)
	defer srv.Close()

	t.Run("missing namespace", func(t *testing.T) {
		result := callTool(t, srv, "get_gitrepository_status", map[string]any{
			"name": "flux-system",
		})
		if !result.IsError {
			t.Error("expected error for missing namespace")
		}
		text := result.Content[0].(mcp.TextContent).Text
		if !strings.Contains(text, "namespace") {
			t.Errorf("expected 'namespace' in error, got: %s", text)
		}
	})

	t.Run("missing name", func(t *testing.T) {
		result := callTool(t, srv, "get_gitrepository_status", map[string]any{
			"namespace": "flux-system",
		})
		if !result.IsError {
			t.Error("expected error for missing name")
		}
		text := result.Content[0].(mcp.TextContent).Text
		if !strings.Contains(text, "name") {
			t.Errorf("expected 'name' in error, got: %s", text)
		}
	})
}

func TestFluxToolInventory(t *testing.T) {
	fake := &fakeFluxClient{}
	cfg := &config.Config{MaxOutputBytesDescribe: 4096}
	mcpSrv := fluxserver.NewFluxServer(fake, cfg)

	tools := mcpSrv.ListTools()
	names := make(map[string]bool, len(tools))
	for _, tool := range tools {
		names[tool.Tool.Name] = true
	}

	required := []string{"reconcile_kustomization", "get_kustomization_status", "get_gitrepository_status"}
	for _, name := range required {
		if !names[name] {
			t.Errorf("expected tool %q to be registered", name)
		}
	}
	if names["suspend_kustomization"] {
		t.Error("suspend_kustomization must not be registered")
	}
	if names["resume_kustomization"] {
		t.Error("resume_kustomization must not be registered")
	}
	if len(tools) != 3 {
		t.Errorf("expected exactly 3 tools, got %d", len(tools))
	}
}
