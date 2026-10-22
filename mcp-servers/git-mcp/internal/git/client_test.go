package git

import (
	"context"
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"github.com/mark3labs/mcp-go/mcp"

	"github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/auth"
	"github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/config"
)

const testRepoURL = "https://github.com/test/test.git"

func newTestClient(token string) GitClient {
	return NewRealGitClient(&config.Config{RepoURL: testRepoURL}, auth.Identity{
		Token:       auth.Static(token),
		AuthorName:  "agent[bot]",
		AuthorEmail: "1+agent[bot]@users.noreply.github.com",
	})
}

func TestSanitiseAuthError_redactsToken(t *testing.T) {
	err := sanitiseAuthError(errors.New("auth failed for supersecret"), "supersecret")
	if strings.Contains(err.Error(), "supersecret") || !strings.Contains(err.Error(), "[redacted]") {
		t.Errorf("token not redacted: %v", err)
	}
	if got := sanitiseAuthError(errors.New("plain"), ""); got.Error() != "plain" {
		t.Errorf("empty token altered message: %v", got)
	}
}

func TestRealGitClient_cloneErrorOmitsToken(t *testing.T) {
	c := newTestClient("supersecret")
	_, err := c.Clone(context.Background(), filepath.Join(t.TempDir(), "missing"), "")
	if err == nil {
		t.Fatal("Clone: expected error, got nil")
	}
	if strings.Contains(err.Error(), "supersecret") {
		t.Errorf("Clone: error leaks token: %v", err)
	}
}

func TestRevertCommit_authorsAsIdentity(t *testing.T) {
	remoteDir, cloneDir := setupRepoWithRemote(t)
	workDir := t.TempDir()
	mustRun(t, workDir, "git", "clone", remoteDir, ".")
	if err := os.WriteFile(filepath.Join(workDir, "f.txt"), []byte("x"), 0o644); err != nil {
		t.Fatal(err)
	}
	mustRun(t, workDir, "git", "add", "f.txt")
	mustRun(t, workDir, "git", "commit", "-m", "add f")
	mustRun(t, workDir, "git", "push", "origin", "main")
	out, err := exec.Command("git", "-C", workDir, "rev-parse", "HEAD").Output()
	if err != nil {
		t.Fatal(err)
	}

	if _, err := newTestClient("tok").RevertCommit(context.Background(), cloneDir, strings.TrimSpace(string(out)), "main"); err != nil {
		t.Fatalf("RevertCommit: %v", err)
	}
	author, err := exec.Command("git", "-C", cloneDir, "log", "-1", "--format=%an <%ae>|%cn <%ce>").Output()
	if err != nil {
		t.Fatal(err)
	}
	want := "agent[bot] <1+agent[bot]@users.noreply.github.com>"
	if got := strings.TrimSpace(string(author)); got != want+"|"+want {
		t.Errorf("revert author|committer = %q, want %q for both", got, want)
	}
}

func TestCommitFiles_authorsAsIdentity(t *testing.T) {
	_, cloneDir := setupRepoWithRemote(t)
	if err := os.WriteFile(filepath.Join(cloneDir, "f.txt"), []byte("x"), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := newTestClient("tok").CommitFiles(context.Background(), cloneDir, "main", "msg"); err != nil {
		t.Fatalf("CommitFiles: %v", err)
	}
	author, err := exec.Command("git", "-C", cloneDir, "log", "-1", "--format=%an <%ae>").Output()
	if err != nil {
		t.Fatal(err)
	}
	if got := strings.TrimSpace(string(author)); got != "agent[bot] <1+agent[bot]@users.noreply.github.com>" {
		t.Errorf("commit author = %q", got)
	}
}

func TestCloneRepoHandler_cloneConfigHoldsNoToken(t *testing.T) {
	const sentinel = "SECRET_TOKEN_FIXTURE"
	remoteDir, _ := setupRepoWithRemote(t)
	state := &cloneOnlyState{}
	handler := HandleCloneRepo(newTestClient(sentinel), state, remoteDir, config.MaxOutputBytesDefault)

	req := mcp.CallToolRequest{}
	req.Params.Arguments = map[string]any{"run_id": "run-1"}
	result, err := handler(context.Background(), req)
	if err != nil || result.IsError {
		t.Fatalf("clone failed: %v %v", err, result.Content)
	}
	defer func() { _ = os.RemoveAll(state.dir) }()
	gitConfig, err := os.ReadFile(filepath.Join(state.dir, ".git", "config"))
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(gitConfig), sentinel) {
		t.Errorf(".git/config holds the token:\n%s", gitConfig)
	}
}

type cloneOnlyState struct{ dir string }

func (s *cloneOnlyState) BeginSession(_, cloneDir string) { s.dir = cloneDir }
func (s *cloneOnlyState) Branch() (string, string)        { return "", s.dir }
func (s *cloneOnlyState) SetBranch(string)                {}
func (s *cloneOnlyState) BaseBranch() string              { return "" }
func (s *cloneOnlyState) SetBaseBranch(string)            {}
func (s *cloneOnlyState) SetLastCommit(string)            {}
func (s *cloneOnlyState) RunID() string                   { return "" }
func (s *cloneOnlyState) CloneDir() string                { return s.dir }

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

	mustRun(t, cloneDir, "git", "config", "user.email", "test@test")
	mustRun(t, cloneDir, "git", "config", "user.name", "test")

	c := newTestClient("tok")
	revertSHA, err := c.RevertCommit(context.Background(), cloneDir, sha, "main")
	if err != nil {
		t.Fatalf("RevertCommit: %v", err)
	}
	if revertSHA == "" {
		t.Error("expected non-empty revert SHA")
	}

	remoteHead, err := exec.Command("git", "-C", remoteDir, "rev-parse", "main").Output()
	if err != nil {
		t.Fatalf("rev-parse origin main: %v", err)
	}
	if strings.TrimSpace(string(remoteHead)) != revertSHA {
		t.Errorf("origin main = %q, want revert SHA %q (push did not reach origin)", strings.TrimSpace(string(remoteHead)), revertSHA)
	}
}

func TestRevertCommit_PushesRevertedContentToOrigin(t *testing.T) {
	remoteDir, cloneDir := setupRepoWithRemote(t)

	workDir := t.TempDir()
	mustRun(t, workDir, "git", "clone", remoteDir, ".")
	if err := os.WriteFile(filepath.Join(workDir, "bad.txt"), []byte("bad"), 0o644); err != nil {
		t.Fatal(err)
	}
	mustRun(t, workDir, "git", "add", "bad.txt")
	mustRun(t, workDir, "git", "commit", "-m", "introduce bad file")
	mustRun(t, workDir, "git", "push", "origin", "main")

	out, err := exec.Command("git", "-C", workDir, "rev-parse", "HEAD").Output()
	if err != nil {
		t.Fatalf("rev-parse: %v", err)
	}
	badSHA := strings.TrimSpace(string(out))

	mustRun(t, cloneDir, "git", "config", "user.email", "test@test")
	mustRun(t, cloneDir, "git", "config", "user.name", "test")

	c := newTestClient("tok")
	if _, err := c.RevertCommit(context.Background(), cloneDir, badSHA, "main"); err != nil {
		t.Fatalf("RevertCommit: %v", err)
	}

	verifyDir := t.TempDir()
	mustRun(t, verifyDir, "git", "clone", remoteDir, ".")
	if _, err := os.Stat(filepath.Join(verifyDir, "bad.txt")); !os.IsNotExist(err) {
		t.Errorf("bad.txt still present on origin after revert; revert did not reach remote (stat err: %v)", err)
	}
}

func TestRevertCommit_FetchFailureReturnsClearError(t *testing.T) {
	cloneDir := t.TempDir()
	mustRun(t, cloneDir, "git", "init", "--initial-branch=main")
	mustRun(t, cloneDir, "git", "remote", "add", "origin", "/nonexistent/path")
	mustRun(t, cloneDir, "git", "commit", "--allow-empty", "-m", "init")

	c := newTestClient("tok")
	_, err := c.RevertCommit(context.Background(), cloneDir, "deadbeef", "main")
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !strings.HasPrefix(err.Error(), "revert_commit: fetch:") {
		t.Errorf("expected 'revert_commit: fetch:' prefix, got: %v", err)
	}
}

func TestCreateBranch_ResetsToFetchedBase(t *testing.T) {
	remoteDir, cloneDir := setupRepoWithRemote(t)

	mustRun(t, cloneDir, "git", "config", "user.email", "test@test")
	mustRun(t, cloneDir, "git", "config", "user.name", "test")

	c := newTestClient("tok")

	if err := c.CreateBranch(context.Background(), cloneDir, "remediation/run-x", "main"); err != nil {
		t.Fatalf("CreateBranch attempt-1: %v", err)
	}
	attemptOneFile := filepath.Join(cloneDir, "attempt-1.txt")
	if err := os.WriteFile(attemptOneFile, []byte("first attempt"), 0o644); err != nil {
		t.Fatal(err)
	}
	mustRun(t, cloneDir, "git", "add", "attempt-1.txt")
	mustRun(t, cloneDir, "git", "commit", "-m", "attempt-1 work")

	advanceDir := t.TempDir()
	mustRun(t, advanceDir, "git", "clone", remoteDir, ".")
	mustRun(t, advanceDir, "git", "config", "user.email", "test@test")
	mustRun(t, advanceDir, "git", "config", "user.name", "test")
	if err := os.WriteFile(filepath.Join(advanceDir, "base.txt"), []byte("base advanced"), 0o644); err != nil {
		t.Fatal(err)
	}
	mustRun(t, advanceDir, "git", "add", "base.txt")
	mustRun(t, advanceDir, "git", "commit", "-m", "advance base")
	mustRun(t, advanceDir, "git", "push", "origin", "main")

	out, err := exec.Command("git", "-C", advanceDir, "rev-parse", "HEAD").Output()
	if err != nil {
		t.Fatalf("rev-parse advanced base: %v", err)
	}
	wantTip := strings.TrimSpace(string(out))

	if err := c.CreateBranch(context.Background(), cloneDir, "remediation/run-y", "main"); err != nil {
		t.Fatalf("CreateBranch attempt-2: %v", err)
	}

	headOut, err := exec.Command("git", "-C", cloneDir, "rev-parse", "HEAD").Output()
	if err != nil {
		t.Fatalf("rev-parse HEAD after attempt-2: %v", err)
	}
	if got := strings.TrimSpace(string(headOut)); got != wantTip {
		t.Errorf("HEAD = %q, want fetched base tip %q", got, wantTip)
	}
	if _, err := os.Stat(attemptOneFile); !os.IsNotExist(err) {
		t.Errorf("attempt-1 file still present on attempt-2 branch (stat err: %v); branch did not reset to base", err)
	}
}

func TestCreateBranch_FetchFailureReturnsClearError(t *testing.T) {
	cloneDir := t.TempDir()
	mustRun(t, cloneDir, "git", "init", "--initial-branch=main")
	mustRun(t, cloneDir, "git", "remote", "add", "origin", "/nonexistent/path")
	mustRun(t, cloneDir, "git", "commit", "--allow-empty", "-m", "init")

	c := newTestClient("tok")
	err := c.CreateBranch(context.Background(), cloneDir, "remediation/run-z", "main")
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !strings.HasPrefix(err.Error(), "create_branch: fetch base") {
		t.Errorf("expected 'create_branch: fetch base' prefix, got: %v", err)
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
