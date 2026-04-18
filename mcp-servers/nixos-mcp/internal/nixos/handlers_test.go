package nixos_test

import (
	"context"
	"strings"
	"testing"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/mcptest"
	"github.com/mark3labs/mcp-go/server"

	"github.com/lucawalz/vigil/mcp-servers/nixos-mcp/internal/nixos"
)

type fakeNixOSClient struct {
	generationsOut   string
	generationsErr   error
	switchOut        string
	switchErr        error
	rebuildOut       string
	rebuildErr       error
	journalOut       string
	journalErr       error
	systemdOut       string
	systemdErr       error
	etcdOut          string
	etcdErr          error
	lastSwitchGen    int
	lastJournalLines int
}

func (f *fakeNixOSClient) GetGenerations(_ context.Context, _ string) (string, error) {
	return f.generationsOut, f.generationsErr
}

func (f *fakeNixOSClient) SwitchGeneration(_ context.Context, _ string, generation int) (string, error) {
	f.lastSwitchGen = generation
	return f.switchOut, f.switchErr
}

func (f *fakeNixOSClient) RebuildTest(_ context.Context, _ string) (string, error) {
	return f.rebuildOut, f.rebuildErr
}

func (f *fakeNixOSClient) GetJournal(_ context.Context, _, _ string, lines int) (string, error) {
	f.lastJournalLines = lines
	return f.journalOut, f.journalErr
}

func (f *fakeNixOSClient) GetSystemdStatus(_ context.Context, _, _ string) (string, error) {
	return f.systemdOut, f.systemdErr
}

func (f *fakeNixOSClient) EtcdSnapshotSave(_ context.Context, _, _ string) (string, error) {
	return f.etcdOut, f.etcdErr
}

func newTestServer(t *testing.T, client nixos.NixOSClient) *mcptest.Server {
	t.Helper()
	srv, err := mcptest.NewServer(t,
		server.ServerTool{
			Tool:    mcp.NewTool("get_generations", mcp.WithString("host", mcp.Required())),
			Handler: nixos.HandleGetGenerations(client, 4096),
		},
		server.ServerTool{
			Tool: mcp.NewTool("switch_generation",
				mcp.WithString("host", mcp.Required()),
				mcp.WithNumber("generation", mcp.Required()),
			),
			Handler: nixos.HandleSwitchGeneration(client, 4096),
		},
		server.ServerTool{
			Tool:    mcp.NewTool("rebuild_test", mcp.WithString("host", mcp.Required())),
			Handler: nixos.HandleRebuildTest(client, 4096),
		},
		server.ServerTool{
			Tool: mcp.NewTool("get_journal",
				mcp.WithString("host", mcp.Required()),
				mcp.WithString("unit", mcp.Required()),
				mcp.WithNumber("lines"),
			),
			Handler: nixos.HandleGetJournal(client, 2048),
		},
		server.ServerTool{
			Tool: mcp.NewTool("get_systemd_status",
				mcp.WithString("host", mcp.Required()),
				mcp.WithString("unit", mcp.Required()),
			),
			Handler: nixos.HandleGetSystemdStatus(client, 4096),
		},
		server.ServerTool{
			Tool: mcp.NewTool("etcd_snapshot_save",
				mcp.WithString("host", mcp.Required()),
				mcp.WithString("dest_path", mcp.Required()),
			),
			Handler: nixos.HandleEtcdSnapshotSave(client, 4096),
		},
	)
	if err != nil {
		t.Fatal(err)
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

func resultText(result *mcp.CallToolResult) string {
	if len(result.Content) == 0 {
		return ""
	}
	if tc, ok := result.Content[0].(mcp.TextContent); ok {
		return tc.Text
	}
	return ""
}

func TestRebuildTestHandler_IncludesHealthGate(t *testing.T) {
	fake := &fakeNixOSClient{
		rebuildOut: "nixos-rebuild exit: 0\nhealth-gate: active (running)\nk8s-node-ready: True",
	}
	srv := newTestServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "rebuild_test", map[string]any{"host": "192.168.1.10"})

	if result.IsError {
		t.Fatalf("expected success, got IsError=true: %s", resultText(result))
	}
	text := resultText(result)
	for _, field := range []string{"nixos-rebuild exit:", "health-gate:", "k8s-node-ready:"} {
		if !strings.Contains(text, field) {
			t.Errorf("response missing required field %q, got: %s", field, text)
		}
	}
}

func TestRebuildTestHandler_FailedRebuild(t *testing.T) {
	fake := &fakeNixOSClient{
		rebuildOut: "nixos-rebuild exit: 1\nhealth-gate: inactive\nk8s-node-ready: False",
	}
	srv := newTestServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "rebuild_test", map[string]any{"host": "192.168.1.10"})

	if result.IsError {
		t.Fatalf("unexpected error: %s", resultText(result))
	}
	if !strings.Contains(resultText(result), "nixos-rebuild exit: 1") {
		t.Errorf("expected exit code 1 in response, got: %s", resultText(result))
	}
}

func TestRebuildTestHandler_DomainError(t *testing.T) {
	fake := &fakeNixOSClient{rebuildErr: context.DeadlineExceeded}
	srv := newTestServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "rebuild_test", map[string]any{"host": "192.168.1.10"})

	if !result.IsError {
		t.Error("expected IsError=true for domain error")
	}
}

func TestGetGenerationsHandler_Success(t *testing.T) {
	fake := &fakeNixOSClient{generationsOut: "1  2024-01-01\n2  2024-02-01 (current)"}
	srv := newTestServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "get_generations", map[string]any{"host": "192.168.1.10"})

	if result.IsError {
		t.Fatalf("unexpected error: %s", resultText(result))
	}
	if !strings.Contains(resultText(result), "current") {
		t.Errorf("expected generation list in response, got: %s", resultText(result))
	}
}

func TestGetGenerationsHandler_Truncation(t *testing.T) {
	fake := &fakeNixOSClient{generationsOut: strings.Repeat("generation-line\n", 1000)}
	srv := newTestServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "get_generations", map[string]any{"host": "192.168.1.10"})

	if result.IsError {
		t.Fatalf("unexpected error")
	}
	if !strings.Contains(resultText(result), "[TRUNCATED:") {
		t.Errorf("expected truncation marker")
	}
}

func TestSwitchGenerationHandler_Success(t *testing.T) {
	fake := &fakeNixOSClient{switchOut: "switched to generation 3"}
	srv := newTestServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "switch_generation", map[string]any{
		"host":       "192.168.1.10",
		"generation": float64(3),
	})

	if result.IsError {
		t.Fatalf("unexpected error: %s", resultText(result))
	}
}

func TestSwitchGenerationHandler_NumericArg(t *testing.T) {
	fake := &fakeNixOSClient{switchOut: "ok"}
	srv := newTestServer(t, fake)
	defer srv.Close()

	callTool(t, srv, "switch_generation", map[string]any{
		"host":       "192.168.1.10",
		"generation": float64(42),
	})

	if fake.lastSwitchGen != 42 {
		t.Errorf("expected generation 42, got %d", fake.lastSwitchGen)
	}
}

func TestGetJournalHandler_Success(t *testing.T) {
	fake := &fakeNixOSClient{journalOut: "Apr 17 k3s[123]: starting"}
	srv := newTestServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "get_journal", map[string]any{
		"host":  "192.168.1.10",
		"unit":  "k3s",
		"lines": float64(50),
	})

	if result.IsError {
		t.Fatalf("unexpected error: %s", resultText(result))
	}
	if !strings.Contains(resultText(result), "k3s") {
		t.Errorf("expected journal output, got: %s", resultText(result))
	}
}

func TestGetSystemdStatusHandler_Success(t *testing.T) {
	fake := &fakeNixOSClient{systemdOut: "● k3s.service - Lightweight Kubernetes\n   Active: active (running)"}
	srv := newTestServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "get_systemd_status", map[string]any{
		"host": "192.168.1.10",
		"unit": "k3s",
	})

	if result.IsError {
		t.Fatalf("unexpected error: %s", resultText(result))
	}
	if !strings.Contains(resultText(result), "active") {
		t.Errorf("expected status output, got: %s", resultText(result))
	}
}

func TestEtcdSnapshotSaveHandler_Success(t *testing.T) {
	fake := &fakeNixOSClient{etcdOut: "Snapshot saved at /backup/etcd.snap"}
	srv := newTestServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "etcd_snapshot_save", map[string]any{
		"host":      "192.168.1.10",
		"dest_path": "/backup/etcd.snap",
	})

	if result.IsError {
		t.Fatalf("unexpected error: %s", resultText(result))
	}
	if !strings.Contains(resultText(result), "Snapshot") {
		t.Errorf("expected snapshot output, got: %s", resultText(result))
	}
}
