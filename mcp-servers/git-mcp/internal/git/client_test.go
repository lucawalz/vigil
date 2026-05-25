package git

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
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

	_, err := c.Clone(ctx, authURL, "")
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

func mustRun(t *testing.T, dir string, args ...string) {
	t.Helper()
	cmd := exec.Command(args[0], args[1:]...)
	cmd.Dir = dir
	cmd.Env = append(os.Environ(),
		"GIT_AUTHOR_NAME=test", "GIT_AUTHOR_EMAIL=test@test",
		"GIT_COMMITTER_NAME=test", "GIT_COMMITTER_EMAIL=test@test",
	)
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("%v: %s", args, out)
	}
}

func setupRepoWithRemote(t *testing.T) (remoteDir, cloneDir string) {
	t.Helper()
	remoteDir = t.TempDir()
	cloneDir = t.TempDir()
	mustRun(t, remoteDir, "git", "init", "--bare", "--initial-branch=main")
	mustRun(t, cloneDir, "git", "init", "--initial-branch=main")
	mustRun(t, cloneDir, "git", "remote", "add", "origin", remoteDir)
	mustRun(t, cloneDir, "git", "commit", "--allow-empty", "-m", "init")
	mustRun(t, cloneDir, "git", "push", "origin", "main")
	return remoteDir, cloneDir
}

func TestRevertCommit_FetchesBeforeRevert(t *testing.T) {
	remoteDir, cloneDir := setupRepoWithRemote(t)

	workDir := t.TempDir()
	mustRun(t, workDir, "git", "clone", remoteDir, ".")
	if err := os.WriteFile(filepath.Join(workDir, "file.txt"), []byte("hello"), 0o644); err != nil {
		t.Fatal(err)
	}
	mustRun(t, workDir, "git", "add", "file.txt")
	mustRun(t, workDir, "git", "commit", "-m", "remote-only commit")
	mustRun(t, workDir, "git", "push", "origin", "main")

	out, err := exec.Command("git", "-C", workDir, "rev-parse", "HEAD").Output()
	if err != nil {
		t.Fatalf("rev-parse: %v", err)
	}
	sha := strings.TrimSpace(string(out))

	cfg := &config.Config{RepoURL: "https://github.com/test/test.git"}
	c := NewRealGitClient(cfg)
	revertSHA, err := c.RevertCommit(context.Background(), cloneDir, sha, "main")
	if err != nil {
		t.Fatalf("RevertCommit: %v", err)
	}
	if revertSHA == "" {
		t.Error("expected non-empty revert SHA")
	}
}

func TestRevertCommit_FetchFailureReturnsClearError(t *testing.T) {
	cloneDir := t.TempDir()
	mustRun(t, cloneDir, "git", "init", "--initial-branch=main")
	mustRun(t, cloneDir, "git", "remote", "add", "origin", "/nonexistent/path")
	mustRun(t, cloneDir, "git", "commit", "--allow-empty", "-m", "init")

	cfg := &config.Config{RepoURL: "https://github.com/test/test.git"}
	c := NewRealGitClient(cfg)
	_, err := c.RevertCommit(context.Background(), cloneDir, "deadbeef", "main")
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !strings.HasPrefix(err.Error(), "revert_commit: fetch:") {
		t.Errorf("expected 'revert_commit: fetch:' prefix, got: %v", err)
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
