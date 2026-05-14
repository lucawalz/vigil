package git

import (
	"context"
	"strings"
	"testing"

	"github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/config"
)

func TestNewRealGitClient_implementsInterface(t *testing.T) {
	cfg := &config.Config{
		GitHubToken: "test-token",
		RepoURL:     "https://github.com/lucawalz/vigil.git",
	}
	var _ GitClient = NewRealGitClient(cfg)
}

func TestRealGitClient_stubsReturnNotImplemented(t *testing.T) {
	cfg := &config.Config{
		GitHubToken: "tok",
		RepoURL:     "https://github.com/lucawalz/vigil.git",
	}
	c := NewRealGitClient(cfg)
	ctx := context.Background()

	if _, err := c.Clone(ctx, "url"); err == nil || !strings.Contains(err.Error(), "not implemented") {
		t.Errorf("Clone: expected not-implemented error, got %v", err)
	}
	if err := c.CreateBranch(ctx, "dir", "branch"); err == nil || !strings.Contains(err.Error(), "not implemented") {
		t.Errorf("CreateBranch: expected not-implemented error, got %v", err)
	}
	if err := c.WriteFile(ctx, "dir", "path", "content"); err == nil || !strings.Contains(err.Error(), "not implemented") {
		t.Errorf("WriteFile: expected not-implemented error, got %v", err)
	}
	if _, err := c.CommitFiles(ctx, "dir", "branch", "msg"); err == nil || !strings.Contains(err.Error(), "not implemented") {
		t.Errorf("CommitFiles: expected not-implemented error, got %v", err)
	}
	if err := c.Push(ctx, "dir", "branch"); err == nil || !strings.Contains(err.Error(), "not implemented") {
		t.Errorf("Push: expected not-implemented error, got %v", err)
	}
	if _, err := c.CreatePR(ctx, "title", "head", "base", "body"); err == nil || !strings.Contains(err.Error(), "not implemented") {
		t.Errorf("CreatePR: expected not-implemented error, got %v", err)
	}
	if _, _, _, err := c.GetPRStatus(ctx, 1); err == nil || !strings.Contains(err.Error(), "not implemented") {
		t.Errorf("GetPRStatus: expected not-implemented error, got %v", err)
	}
	if _, err := c.RevertCommit(ctx, "dir", "sha"); err == nil || !strings.Contains(err.Error(), "not implemented") {
		t.Errorf("RevertCommit: expected not-implemented error, got %v", err)
	}
}

func TestTruncateOutput_noTruncation(t *testing.T) {
	s := "hello"
	got := truncateOutput(s, 100)
	if got != s {
		t.Errorf("truncateOutput(%q, 100) = %q, want %q", s, got, s)
	}
}

func TestTruncateOutput_truncates(t *testing.T) {
	s := "line1\nline2\nline3\nline4\nline5"
	got := truncateOutput(s, 10)
	if !strings.Contains(got, "[TRUNCATED:") {
		t.Errorf("truncateOutput did not truncate: %q", got)
	}
}
