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
	var _ = NewRealGitClient(cfg)
}

func TestRealGitClient_errorPathsSanitiseURL(t *testing.T) {
	cfg := &config.Config{
		GitHubToken: "supersecret",
		RepoURL:     "https://github.com/lucawalz/vigil.git",
	}
	c := NewRealGitClient(cfg)
	ctx := context.Background()

	authURL := cfg.AuthURL()

	_, err := c.Clone(ctx, authURL)
	if err == nil {
		t.Fatal("Clone: expected error, got nil")
	}
	if strings.Contains(err.Error(), "supersecret") {
		t.Errorf("Clone: error leaks token: %v", err)
	}
	if strings.Contains(err.Error(), authURL) {
		t.Errorf("Clone: error leaks authURL: %v", err)
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
