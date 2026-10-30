package server

import (
	"context"
	"os"
	"testing"

	"github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/config"
	"github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/git"
)

type fakeGitClient struct{}

func (f *fakeGitClient) Clone(_ context.Context, _, _ string) (string, error) { return "", nil }
func (f *fakeGitClient) CreateBranch(_ context.Context, _, _, _ string) error { return nil }
func (f *fakeGitClient) WriteFile(_ context.Context, _, _, _ string) error    { return nil }
func (f *fakeGitClient) CommitFiles(_ context.Context, _, _, _ string) (string, error) {
	return "", nil
}
func (f *fakeGitClient) Push(_ context.Context, _, _ string) error                  { return nil }
func (f *fakeGitClient) CreatePR(_ context.Context, _, _, _, _ string) (int, error) { return 0, nil }
func (f *fakeGitClient) GetPRStatus(_ context.Context, _ int) (string, bool, string, error) {
	return "", false, "", nil
}
func (f *fakeGitClient) MergePR(_ context.Context, _ int, _ string) (string, error) { return "", nil }
func (f *fakeGitClient) RevertCommit(_ context.Context, _, _, _, _ string) (string, error) {
	return "", nil
}
func (f *fakeGitClient) ClosePR(_ context.Context, _ int) error                     { return nil }
func (f *fakeGitClient) DeleteBranch(_ context.Context, _ string) error             { return nil }
func (f *fakeGitClient) ReadFile(_ context.Context, _, _, _ string) (string, error) { return "", nil }
func (f *fakeGitClient) ResolveManifestPath(_ context.Context, _, _, _, _, _ string) (string, string, error) {
	return "", "", nil
}
func (f *fakeGitClient) GetCheckRunStatus(_ context.Context, _ int) (bool, string, string, error) {
	return false, "", "", nil
}
func (f *fakeGitClient) GetMergeableState(_ context.Context, _ int) (string, error) {
	return "", nil
}

var _ git.GitClient = &fakeGitClient{}

func TestServerRegisters13Tools(t *testing.T) {
	cfg := &config.Config{
		GitHubToken:    "tok",
		RepoURL:        "https://github.com/lucawalz/vigil.git",
		MaxOutputBytes: 4096,
	}
	client := &fakeGitClient{}
	mcpSrv, _ := NewServer(client, cfg, config.DefaultWaitForGateTimeoutSeconds)
	if mcpSrv == nil {
		t.Fatal("NewServer returned nil")
	}

	tools := mcpSrv.ListTools()
	want := map[string]bool{
		"clone_repo":            true,
		"create_branch":         true,
		"write_manifest":        true,
		"commit_files":          true,
		"push_branch":           true,
		"create_pr":             true,
		"get_pr_status":         true,
		"wait_for_gate":         true,
		"revert_commit":         true,
		"close_pr":              true,
		"delete_branch":         true,
		"read_file":             true,
		"resolve_manifest_path": true,
	}
	if len(tools) != len(want) {
		t.Errorf("expected %d tools, got %d", len(want), len(tools))
	}
	for name := range want {
		if _, ok := tools[name]; !ok {
			t.Errorf("missing tool: %s", name)
		}
	}
}

func TestServer_gateToolsTakeOnlyTheirTarget(t *testing.T) {
	cfg := &config.Config{GitHubToken: "tok", RepoURL: "https://github.com/lucawalz/vigil.git", MaxOutputBytes: 4096}
	mcpSrv, _ := NewServer(&fakeGitClient{}, cfg, config.DefaultWaitForGateTimeoutSeconds)
	tools := mcpSrv.ListTools()
	want := map[string][]string{
		"create_pr":     {"title", "body"},
		"wait_for_gate": {"pr_number"},
		"revert_commit": {"merge_commit_sha"},
	}
	for name, params := range want {
		props := tools[name].Tool.InputSchema.Properties
		if len(props) != len(params) {
			t.Errorf("%s parameters = %v, want only %v", name, props, params)
		}
		for _, p := range params {
			if _, ok := props[p]; !ok {
				t.Errorf("%s is missing parameter %s", name, p)
			}
		}
	}
}

func TestGitServer_sessionFields(t *testing.T) {
	s := &GitServer{
		currentBranch: "remediation/run-abc",
		lastCommitSHA: "deadbeef",
		runID:         "abc",
		cloneDir:      "/tmp/clone",
	}
	if s.currentBranch != "remediation/run-abc" {
		t.Errorf("currentBranch mismatch")
	}
	if s.lastCommitSHA != "deadbeef" {
		t.Errorf("lastCommitSHA mismatch")
	}
	if s.runID != "abc" {
		t.Errorf("runID mismatch")
	}
	if s.cloneDir != "/tmp/clone" {
		t.Errorf("cloneDir mismatch")
	}
}

func TestGitServer_beginSessionResetsRunState(t *testing.T) {
	s := &GitServer{
		currentBranch: "remediation/run-a",
		baseBranch:    "old",
		lastCommitSHA: "deadbeef",
		runID:         "a",
		cloneDir:      "/tmp/a",
		prNumber:      7,
	}
	s.BeginSession("b", "/tmp/b")
	if s.runID != "b" || s.cloneDir != "/tmp/b" {
		t.Errorf("session identity not set: %q %q", s.runID, s.cloneDir)
	}
	if s.currentBranch != "" || s.baseBranch != "" || s.lastCommitSHA != "" || s.prNumber != 0 {
		t.Errorf("run state not reset: %+v", s)
	}
}

func TestGitServer_closeRemovesTheClone(t *testing.T) {
	dir := t.TempDir()
	s := &GitServer{}
	s.BeginSession("run-1", dir)
	s.Close()
	if _, err := os.Stat(dir); !os.IsNotExist(err) {
		t.Errorf("clone dir still present: %v", err)
	}
	if s.CloneDir() != "" || s.RunID() != "" {
		t.Errorf("session not reset: %q %q", s.CloneDir(), s.RunID())
	}
	s.Close()
}
