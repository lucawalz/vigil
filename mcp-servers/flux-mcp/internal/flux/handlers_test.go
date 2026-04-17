package flux_test

import (
	"context"
	"testing"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/mcptest"
	"github.com/mark3labs/mcp-go/server"

	"github.com/lucawalz/vigil/mcp-servers/flux-mcp/internal/config"
	"github.com/lucawalz/vigil/mcp-servers/flux-mcp/internal/flux"
	fluxserver "github.com/lucawalz/vigil/mcp-servers/flux-mcp/internal/server"
)

type fakeFluxClient struct {
	suspendErr      error
	resumeErr       error
	reconcileResult string
	reconcileErr    error
	statusResult    string
	statusErr       error
}

func (f *fakeFluxClient) SuspendKustomization(_ context.Context, _, _ string) error {
	return f.suspendErr
}
func (f *fakeFluxClient) ResumeKustomization(_ context.Context, _, _ string) error {
	return f.resumeErr
}
func (f *fakeFluxClient) ReconcileKustomization(_ context.Context, _, _ string) (string, error) {
	return f.reconcileResult, f.reconcileErr
}
func (f *fakeFluxClient) GetKustomizationStatus(_ context.Context, _, _ string) (string, error) {
	return f.statusResult, f.statusErr
}

// buildTestServer returns a FluxServer-backed MCPServer for testing via mcptest.
func buildTestMCPServer(t *testing.T, fake flux.FluxClient) *mcptest.Server {
	t.Helper()
	cfg := &config.Config{MaxOutputBytesDescribe: 4096}
	mcpSrv := fluxserver.NewFluxServer(fake, cfg)

	// Collect tools from the MCPServer and create an mcptest server.
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

func TestFluxGuard_ReconcileRefusedWithoutSuspend(t *testing.T) {
	fake := &fakeFluxClient{reconcileResult: "ok"}
	srv := buildTestMCPServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "reconcile_kustomization", map[string]any{
		"namespace": "flux-system", "name": "infra",
	})
	if !result.IsError {
		t.Error("expected IsError=true when guard not set")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !containsStr(text, "flux_suspended guard") {
		t.Errorf("expected guard message, got: %s", text)
	}
}

func TestFluxGuard_ResumeRefusedWithoutSuspend(t *testing.T) {
	fake := &fakeFluxClient{}
	srv := buildTestMCPServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "resume_kustomization", map[string]any{
		"namespace": "flux-system", "name": "infra",
	})
	if !result.IsError {
		t.Error("expected IsError=true when guard not set")
	}
}

func TestFluxGuard_ReconcileAllowedAfterSuspend(t *testing.T) {
	fake := &fakeFluxClient{reconcileResult: "reconcile requested"}
	srv := buildTestMCPServer(t, fake)
	defer srv.Close()

	// Suspend first
	r := callTool(t, srv, "suspend_kustomization", map[string]any{
		"namespace": "flux-system", "name": "infra",
	})
	if r.IsError {
		t.Fatalf("suspend failed: %v", r.Content)
	}

	// Now reconcile should succeed
	r2 := callTool(t, srv, "reconcile_kustomization", map[string]any{
		"namespace": "flux-system", "name": "infra",
	})
	if r2.IsError {
		t.Errorf("expected reconcile to succeed after suspend, got error: %v", r2.Content)
	}
}

func TestFluxGuard_ResumeResetsFlag(t *testing.T) {
	fake := &fakeFluxClient{reconcileResult: "ok"}
	srv := buildTestMCPServer(t, fake)
	defer srv.Close()

	callTool(t, srv, "suspend_kustomization", map[string]any{"namespace": "flux-system", "name": "infra"})
	callTool(t, srv, "resume_kustomization", map[string]any{"namespace": "flux-system", "name": "infra"})

	// Flag should be reset — reconcile must fail again
	result := callTool(t, srv, "reconcile_kustomization", map[string]any{
		"namespace": "flux-system", "name": "infra",
	})
	if !result.IsError {
		t.Error("expected guard to block reconcile after full resume")
	}
}

func TestFluxGuard_MultiSuspendPartialResume(t *testing.T) {
	fake := &fakeFluxClient{reconcileResult: "ok"}
	srv := buildTestMCPServer(t, fake)
	defer srv.Close()

	callTool(t, srv, "suspend_kustomization", map[string]any{"namespace": "flux-system", "name": "a"})
	callTool(t, srv, "suspend_kustomization", map[string]any{"namespace": "flux-system", "name": "b"})
	callTool(t, srv, "resume_kustomization", map[string]any{"namespace": "flux-system", "name": "a"})

	// "b" still suspended — flag still set, reconcile should succeed
	result := callTool(t, srv, "reconcile_kustomization", map[string]any{
		"namespace": "flux-system", "name": "b",
	})
	if result.IsError {
		t.Error("expected reconcile to succeed while 'b' still suspended")
	}
}

func TestGetKustomizationStatus_NoGuard(t *testing.T) {
	fake := &fakeFluxClient{statusResult: "Kustomization: flux-system/infra\nSuspended: true\n"}
	srv := buildTestMCPServer(t, fake)
	defer srv.Close()

	// No suspend called — status should still work
	result := callTool(t, srv, "get_kustomization_status", map[string]any{
		"namespace": "flux-system", "name": "infra",
	})
	if result.IsError {
		t.Errorf("get_kustomization_status should not be guarded, got error: %v", result.Content)
	}
}

func containsStr(s, sub string) bool {
	return len(s) >= len(sub) && (s == sub || len(s) > 0 && func() bool {
		for i := 0; i <= len(s)-len(sub); i++ {
			if s[i:i+len(sub)] == sub {
				return true
			}
		}
		return false
	}())
}
