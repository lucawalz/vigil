package nixos_test

import (
	"context"
	"errors"
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
	stageOut         string
	stageErr         error
	commitOut        string
	commitErr        error
	rebuildOut       string
	rebuildErr       error
	journalOut       string
	journalErr       error
	systemdOut       string
	systemdErr       error
	sysctlOut        string
	sysctlErr        error
	etcdOut          string
	etcdErr          error
	nixPathOut       string
	nixPathErr       error
	dryBuildOut      string
	dryBuildErr      error
	reconcileOut     string
	reconcileErr     error
	lastStageGen     int
	lastJournalUnit  string
	lastJournalLines int
	lastSysctlKey    string
}

func (f *fakeNixOSClient) GetGenerations(_ context.Context, _ string) (string, error) {
	return f.generationsOut, f.generationsErr
}

func (f *fakeNixOSClient) StageGeneration(_ context.Context, _ string, generation int) (string, error) {
	f.lastStageGen = generation
	return f.stageOut, f.stageErr
}

func (f *fakeNixOSClient) CommitGeneration(_ context.Context, _ string) (string, error) {
	return f.commitOut, f.commitErr
}

func (f *fakeNixOSClient) RebuildTest(_ context.Context, _ string) (string, error) {
	return f.rebuildOut, f.rebuildErr
}

func (f *fakeNixOSClient) GetJournal(_ context.Context, _ string, unit string, lines int) (string, error) {
	f.lastJournalUnit = unit
	f.lastJournalLines = lines
	return f.journalOut, f.journalErr
}

func (f *fakeNixOSClient) GetSystemdStatus(_ context.Context, _, _ string) (string, error) {
	return f.systemdOut, f.systemdErr
}

func (f *fakeNixOSClient) GetSysctl(_ context.Context, _ string, key string) (string, error) {
	f.lastSysctlKey = key
	return f.sysctlOut, f.sysctlErr
}

func (f *fakeNixOSClient) EtcdSnapshotSave(_ context.Context, _, _ string) (string, error) {
	return f.etcdOut, f.etcdErr
}

func (f *fakeNixOSClient) GetNixPath(_ context.Context, _ string) (string, error) {
	return f.nixPathOut, f.nixPathErr
}

func (f *fakeNixOSClient) DryBuild(_ context.Context, _ string) (string, error) {
	return f.dryBuildOut, f.dryBuildErr
}

func (f *fakeNixOSClient) TriggerReconcile(_ context.Context, _ string) (string, error) {
	return f.reconcileOut, f.reconcileErr
}

func newTestServer(t *testing.T, client nixos.NixOSClient) *mcptest.Server {
	t.Helper()
	srv, err := mcptest.NewServer(t,
		server.ServerTool{
			Tool:    mcp.NewTool("get_generations", mcp.WithString("host", mcp.Required())),
			Handler: nixos.HandleGetGenerations(client, 4096),
		},
		server.ServerTool{
			Tool: mcp.NewTool("stage_generation",
				mcp.WithString("host", mcp.Required()),
				mcp.WithNumber("generation", mcp.Required()),
			),
			Handler: nixos.HandleStageGeneration(client, 4096),
		},
		server.ServerTool{
			Tool:    mcp.NewTool("commit_generation", mcp.WithString("host", mcp.Required())),
			Handler: nixos.HandleCommitGeneration(client, 4096),
		},
		server.ServerTool{
			Tool:    mcp.NewTool("rebuild_test", mcp.WithString("host", mcp.Required())),
			Handler: nixos.HandleRebuildTest(client, 4096),
		},
		server.ServerTool{
			Tool: mcp.NewTool("get_journal",
				mcp.WithString("host", mcp.Required()),
				mcp.WithString("unit"),
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
			Tool: mcp.NewTool("get_sysctl",
				mcp.WithString("host", mcp.Required()),
				mcp.WithString("key", mcp.Required()),
			),
			Handler: nixos.HandleGetSysctl(client, 4096),
		},
		server.ServerTool{
			Tool: mcp.NewTool("etcd_snapshot_save",
				mcp.WithString("host", mcp.Required()),
				mcp.WithString("dest_path", mcp.Required()),
			),
			Handler: nixos.HandleEtcdSnapshotSave(client, 4096),
		},
		server.ServerTool{
			Tool:    mcp.NewTool("get_nix_path", mcp.WithString("hostname", mcp.Required())),
			Handler: nixos.HandleGetNixPath(client, 4096),
		},
		server.ServerTool{
			Tool:    mcp.NewTool("dry_build", mcp.WithString("host", mcp.Required())),
			Handler: nixos.HandleDryBuild(client, 4096),
		},
		server.ServerTool{
			Tool:    mcp.NewTool("trigger_reconcile", mcp.WithString("host", mcp.Required())),
			Handler: nixos.HandleTriggerReconcile(client, 4096),
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

func TestStageGenerationHandler_Success(t *testing.T) {
	fake := &fakeNixOSClient{stageOut: "staged generation 3"}
	srv := newTestServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "stage_generation", map[string]any{
		"host":       "192.168.1.10",
		"generation": float64(3),
	})

	if result.IsError {
		t.Fatalf("unexpected error: %s", resultText(result))
	}
}

func TestStageGenerationHandler_NumericArg(t *testing.T) {
	fake := &fakeNixOSClient{stageOut: "ok"}
	srv := newTestServer(t, fake)
	defer srv.Close()

	callTool(t, srv, "stage_generation", map[string]any{
		"host":       "192.168.1.10",
		"generation": float64(42),
	})

	if fake.lastStageGen != 42 {
		t.Errorf("expected generation 42, got %d", fake.lastStageGen)
	}
}

func TestStageGenerationHandler_DomainError(t *testing.T) {
	fake := &fakeNixOSClient{stageErr: errors.New("ssh dial failed")}
	srv := newTestServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "stage_generation", map[string]any{
		"host":       "192.168.1.10",
		"generation": float64(3),
	})

	if !result.IsError {
		t.Error("expected IsError=true for domain error")
	}
	if !strings.Contains(resultText(result), "StageGeneration") {
		t.Errorf("expected 'StageGeneration' in response, got: %s", resultText(result))
	}
}

func TestStageGenerationHandler_MissingGeneration(t *testing.T) {
	fake := &fakeNixOSClient{}
	srv := newTestServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "stage_generation", map[string]any{"host": "192.168.1.10"})

	if !result.IsError {
		t.Error("expected IsError=true for missing generation")
	}
	if !strings.Contains(resultText(result), "generation") {
		t.Errorf("expected 'generation' in response, got: %s", resultText(result))
	}
}

func TestCommitGenerationHandler_Success(t *testing.T) {
	fake := &fakeNixOSClient{commitOut: "committed to bootloader"}
	srv := newTestServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "commit_generation", map[string]any{"host": "192.168.1.10"})

	if result.IsError {
		t.Fatalf("unexpected error: %s", resultText(result))
	}
	if !strings.Contains(resultText(result), "committed") {
		t.Errorf("expected commit output, got: %s", resultText(result))
	}
}

func TestCommitGenerationHandler_DomainError(t *testing.T) {
	fake := &fakeNixOSClient{commitErr: errors.New("ssh dial failed")}
	srv := newTestServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "commit_generation", map[string]any{"host": "192.168.1.10"})

	if !result.IsError {
		t.Error("expected IsError=true for domain error")
	}
	if !strings.Contains(resultText(result), "CommitGeneration") {
		t.Errorf("expected 'CommitGeneration' in response, got: %s", resultText(result))
	}
}

func TestCommitGenerationHandler_MissingHost(t *testing.T) {
	fake := &fakeNixOSClient{}
	srv := newTestServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "commit_generation", map[string]any{})

	if !result.IsError {
		t.Error("expected IsError=true for missing host")
	}
	if !strings.Contains(resultText(result), "host") {
		t.Errorf("expected 'host' in response, got: %s", resultText(result))
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

func TestGetJournalHandler_NoUnit(t *testing.T) {
	fake := &fakeNixOSClient{journalOut: "May 28 kernel: boot complete"}
	srv := newTestServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "get_journal", map[string]any{
		"host":  "192.168.1.10",
		"lines": float64(25),
	})

	if result.IsError {
		t.Fatalf("expected success without unit arg, got IsError=true: %s", resultText(result))
	}
	if fake.lastJournalUnit != "" {
		t.Errorf("expected empty unit forwarded to client, got %q", fake.lastJournalUnit)
	}
	if fake.lastJournalLines != 25 {
		t.Errorf("expected lines=25, got %d", fake.lastJournalLines)
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

func TestGetSysctlHandler_Success(t *testing.T) {
	fake := &fakeNixOSClient{sysctlOut: "net.bridge.bridge-nf-call-iptables = 1"}
	srv := newTestServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "get_sysctl", map[string]any{
		"host": "192.168.1.10",
		"key":  "net.bridge.bridge-nf-call-iptables",
	})

	if result.IsError {
		t.Fatalf("unexpected error: %s", resultText(result))
	}
	if !strings.Contains(resultText(result), "net.bridge.bridge-nf-call-iptables = 1") {
		t.Errorf("expected sysctl value in response, got: %s", resultText(result))
	}
	if fake.lastSysctlKey != "net.bridge.bridge-nf-call-iptables" {
		t.Errorf("expected key forwarded to client, got %q", fake.lastSysctlKey)
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

func TestGetNixPathHandler_Success(t *testing.T) {
	fake := &fakeNixOSClient{nixPathOut: "infra/nixos/hosts/hetzner-worker-1/default.nix"}
	srv := newTestServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "get_nix_path", map[string]any{"hostname": "hetzner-worker-1"})

	if result.IsError {
		t.Fatalf("expected success, got IsError=true: %s", resultText(result))
	}
	if !strings.Contains(resultText(result), "infra/nixos/hosts/hetzner-worker-1/default.nix") {
		t.Errorf("expected path in response, got: %s", resultText(result))
	}
}

func TestGetNixPathHandler_UnknownHost(t *testing.T) {
	fake := &fakeNixOSClient{nixPathErr: errors.New(`unknown hostname: "bogus"`)}
	srv := newTestServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "get_nix_path", map[string]any{"hostname": "bogus"})

	if !result.IsError {
		t.Error("expected IsError=true for unknown hostname")
	}
	if !strings.Contains(resultText(result), "unknown hostname") {
		t.Errorf("expected 'unknown hostname' in response, got: %s", resultText(result))
	}
}

func TestGetNixPathHandler_MissingHostname(t *testing.T) {
	fake := &fakeNixOSClient{}
	srv := newTestServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "get_nix_path", map[string]any{})

	if !result.IsError {
		t.Error("expected IsError=true for missing hostname")
	}
	if !strings.Contains(resultText(result), "hostname") {
		t.Errorf("expected 'hostname' in response, got: %s", resultText(result))
	}
}

func TestDryBuildHandler(t *testing.T) {
	fake := &fakeNixOSClient{dryBuildOut: "nothing to activate"}
	srv := newTestServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "dry_build", map[string]any{"host": "hetzner-worker-1"})

	if result.IsError {
		t.Fatalf("expected success, got IsError=true: %s", resultText(result))
	}
	if !strings.Contains(resultText(result), "nothing to activate") {
		t.Errorf("expected output in response, got: %s", resultText(result))
	}
}

func TestDryBuildHandler_WithDiff(t *testing.T) {
	fake := &fakeNixOSClient{dryBuildOut: "would restart the following units: vigil-orchestrator.service"}
	srv := newTestServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "dry_build", map[string]any{"host": "hetzner-worker-1"})

	if result.IsError {
		t.Fatalf("expected success, got IsError=true: %s", resultText(result))
	}
	if !strings.Contains(resultText(result), "vigil-orchestrator.service") {
		t.Errorf("expected unit name in response, got: %s", resultText(result))
	}
}

func TestDryBuildHandler_DomainError(t *testing.T) {
	fake := &fakeNixOSClient{dryBuildErr: errors.New("ssh dial failed")}
	srv := newTestServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "dry_build", map[string]any{"host": "hetzner-worker-1"})

	if !result.IsError {
		t.Error("expected IsError=true for domain error")
	}
	if !strings.Contains(resultText(result), "DryBuild") {
		t.Errorf("expected 'DryBuild' in response, got: %s", resultText(result))
	}
}

func TestTriggerReconcileHandler(t *testing.T) {
	fake := &fakeNixOSClient{reconcileOut: "issued: systemctl start --no-block vigil-auto-reconcile.service\nresponse: "}
	srv := newTestServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "trigger_reconcile", map[string]any{"host": "hetzner-worker-1"})

	if result.IsError {
		t.Fatalf("expected success, got IsError=true: %s", resultText(result))
	}
	if !strings.Contains(resultText(result), "issued:") {
		t.Errorf("expected 'issued:' in response, got: %s", resultText(result))
	}
}

func TestTriggerReconcileHandler_UnitNotFound(t *testing.T) {
	fake := &fakeNixOSClient{reconcileErr: errors.New("trigger_reconcile: ssh: command exited with code 5")}
	srv := newTestServer(t, fake)
	defer srv.Close()

	result := callTool(t, srv, "trigger_reconcile", map[string]any{"host": "hetzner-worker-1"})

	if !result.IsError {
		t.Error("expected IsError=true for unit not found")
	}
	if !strings.Contains(resultText(result), "TriggerReconcile") {
		t.Errorf("expected 'TriggerReconcile' in response, got: %s", resultText(result))
	}
}
