package server

import (
	"context"
	"testing"

	"github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/config"
	"github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/git"
)

type fakeGitClient struct{}

func (f *fakeGitClient) Clone(_ context.Context, _ string) (string, error) { return "", nil }
func (f *fakeGitClient) CreateBranch(_ context.Context, _, _ string) error { return nil }
func (f *fakeGitClient) WriteFile(_ context.Context, _, _, _ string) error { return nil }
func (f *fakeGitClient) CommitFiles(_ context.Context, _, _, _ string) (string, error) {
	return "", nil
}
func (f *fakeGitClient) Push(_ context.Context, _, _ string) error                  { return nil }
func (f *fakeGitClient) CreatePR(_ context.Context, _, _, _, _ string) (int, error) { return 0, nil }
func (f *fakeGitClient) GetPRStatus(_ context.Context, _ int) (string, bool, string, error) {
	return "", false, "", nil
}
func (f *fakeGitClient) RevertCommit(_ context.Context, _, _ string) (string, error) { return "", nil }

var _ git.GitClient = &fakeGitClient{}

func TestNewServer_registersEightTools(t *testing.T) {
	cfg := &config.Config{
		GitHubToken:    "tok",
		RepoURL:        "https://github.com/lucawalz/vigil.git",
		MaxOutputBytes: 4096,
	}
	client := &fakeGitClient{}
	mcpSrv := NewServer(client, cfg)
	if mcpSrv == nil {
		t.Fatal("NewServer returned nil")
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
