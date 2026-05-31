package server

import (
	"context"
	"testing"

	"github.com/lucawalz/vigil/mcp-servers/nixos-mcp/internal/config"
	"github.com/lucawalz/vigil/mcp-servers/nixos-mcp/internal/nixos"
)

type fakeNixOSClient struct{}

var _ nixos.NixOSClient = &fakeNixOSClient{}

func (f *fakeNixOSClient) GetGenerations(_ context.Context, _ string) (string, error) { return "", nil }
func (f *fakeNixOSClient) SwitchGeneration(_ context.Context, _ string, _ int) (string, error) {
	return "", nil
}
func (f *fakeNixOSClient) RebuildTest(_ context.Context, _ string) (string, error) { return "", nil }
func (f *fakeNixOSClient) GetJournal(_ context.Context, _, _ string, _ int) (string, error) {
	return "", nil
}
func (f *fakeNixOSClient) GetSystemdStatus(_ context.Context, _, _ string) (string, error) {
	return "", nil
}
func (f *fakeNixOSClient) GetSysctl(_ context.Context, _, _ string) (string, error) {
	return "", nil
}
func (f *fakeNixOSClient) EtcdSnapshotSave(_ context.Context, _, _ string) (string, error) {
	return "", nil
}
func (f *fakeNixOSClient) GetNixPath(_ context.Context, _ string) (string, error) { return "", nil }
func (f *fakeNixOSClient) DryBuild(_ context.Context, _ string) (string, error)   { return "", nil }
func (f *fakeNixOSClient) TriggerReconcile(_ context.Context, _ string) (string, error) {
	return "", nil
}

func TestNixOSToolInventory(t *testing.T) {
	cfg := &config.Config{MaxOutputBytesDescribe: 4096, MaxOutputBytesLogs: 4096}
	s := NewServer(&fakeNixOSClient{}, cfg)
	tools := s.ListTools()
	want := map[string]bool{
		"get_generations":    true,
		"switch_generation":  true,
		"rebuild_test":       true,
		"get_journal":        true,
		"get_systemd_status": true,
		"get_sysctl":         true,
		"etcd_snapshot_save": true,
		"get_nix_path":       true,
		"dry_build":          true,
		"trigger_reconcile":  true,
	}
	if len(tools) != len(want) {
		t.Errorf("expected %d registered tools, got %d", len(want), len(tools))
	}
	for name := range want {
		if _, ok := tools[name]; !ok {
			t.Errorf("tool %q not registered", name)
		}
	}
}
