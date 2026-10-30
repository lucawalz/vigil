package git

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"

	gogithub "github.com/google/go-github/v86/github"
	"github.com/mark3labs/mcp-go/mcp"

	"github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/auth"
	"github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/config"
)

const (
	testRepoURL      = "https://github.com/test/test.git"
	testRevertBranch = "remediation/revert-test"
	checkRunPageSize = 30
	gateHeadSHA      = "abc123"
)

func newTestClient(token string) GitClient {
	return NewRealGitClient(&config.Config{RepoURL: testRepoURL}, auth.Identity{
		Token:       auth.Static(token),
		AuthorName:  "agent[bot]",
		AuthorEmail: "1+agent[bot]@users.noreply.github.com",
	})
}

func TestGitEnv_resetsInheritedCredentialHelpers(t *testing.T) {
	dir := t.TempDir()
	globalConfig := filepath.Join(dir, "gitconfig")
	if err := os.WriteFile(globalConfig, []byte("[credential]\n\thelper = inherited\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	t.Setenv("GIT_CONFIG_GLOBAL", globalConfig)

	cmd := exec.Command("git", "config", "--get-all", "credential.helper")
	cmd.Env = newTestClient("agent-token").(*realGitClient).gitEnv("agent-token")
	out, err := cmd.Output()
	if err != nil {
		t.Fatalf("git config: %v", err)
	}
	helpers := strings.Split(strings.TrimSuffix(string(out), "\n"), "\n")
	if last := helpers[len(helpers)-1]; last != "" {
		t.Errorf("last credential.helper entry = %q, want an empty reset after inherited helpers %q", last, helpers)
	}
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

func TestSanitiseAuthError_redactsExtraHeaderCredentials(t *testing.T) {
	encoded := base64.StdEncoding.EncodeToString([]byte("x-access-token:supersecret"))
	err := sanitiseAuthError(errors.New("header AUTHORIZATION: basic "+encoded), "supersecret")
	if strings.Contains(err.Error(), encoded) || !strings.Contains(err.Error(), "[redacted]") {
		t.Errorf("encoded credentials not redacted: %v", err)
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

	if _, err := newTestClient("tok").RevertCommit(context.Background(), cloneDir, strings.TrimSpace(string(out)), "main", testRevertBranch); err != nil {
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
	revertSHA, err := c.RevertCommit(context.Background(), cloneDir, sha, "main", testRevertBranch)
	if err != nil {
		t.Fatalf("RevertCommit: %v", err)
	}
	if revertSHA == "" {
		t.Error("expected non-empty revert SHA")
	}

	if got := remoteRef(t, remoteDir, testRevertBranch); got != revertSHA {
		t.Errorf("origin %s = %q, want revert SHA %q", testRevertBranch, got, revertSHA)
	}
	if got := remoteRef(t, remoteDir, "main"); got != sha {
		t.Errorf("origin main = %q, want it to stay at %q", got, sha)
	}
}

func remoteRef(t *testing.T, remoteDir, branch string) string {
	t.Helper()
	out, err := exec.Command("git", "-C", remoteDir, "rev-parse", branch).Output()
	if err != nil {
		t.Fatalf("rev-parse %s: %v", branch, err)
	}
	return strings.TrimSpace(string(out))
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
	if _, err := c.RevertCommit(context.Background(), cloneDir, badSHA, "main", testRevertBranch); err != nil {
		t.Fatalf("RevertCommit: %v", err)
	}

	verifyDir := t.TempDir()
	mustRun(t, verifyDir, "git", "clone", "--branch", testRevertBranch, remoteDir, ".")
	if _, err := os.Stat(filepath.Join(verifyDir, "bad.txt")); !os.IsNotExist(err) {
		t.Errorf("bad.txt present on the revert branch (stat err: %v)", err)
	}
}

func TestRevertCommit_FetchFailureReturnsClearError(t *testing.T) {
	cloneDir := t.TempDir()
	mustRun(t, cloneDir, "git", "init", "--initial-branch=main")
	mustRun(t, cloneDir, "git", "remote", "add", "origin", "/nonexistent/path")
	mustRun(t, cloneDir, "git", "commit", "--allow-empty", "-m", "init")

	c := newTestClient("tok")
	_, err := c.RevertCommit(context.Background(), cloneDir, "deadbeef", "main", testRevertBranch)
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

func newGitHubStubClient(t *testing.T, pullRequestJSON string, graphQLCalls *int) *realGitClient {
	t.Helper()
	mux := http.NewServeMux()
	mux.HandleFunc("GET /repos/test/test/pulls/7", func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write([]byte(pullRequestJSON))
	})
	mux.HandleFunc("POST /graphql", func(w http.ResponseWriter, _ *http.Request) {
		*graphQLCalls++
		_, _ = w.Write([]byte(`{"data":{}}`))
	})
	srv := httptest.NewServer(mux)
	t.Cleanup(srv.Close)
	gh := gogithub.NewClient(srv.Client())
	baseURL, err := url.Parse(srv.URL + "/")
	if err != nil {
		t.Fatal(err)
	}
	gh.BaseURL = baseURL
	return &realGitClient{gh: gh, owner: "test", repo: "test"}
}

func TestDisableAutoMerge_skipsMutationWithoutAutoMergeRequest(t *testing.T) {
	graphQLCalls := 0
	client := newGitHubStubClient(t, `{"number":7,"node_id":"PR_7"}`, &graphQLCalls)

	if err := client.DisableAutoMerge(context.Background(), 7); err != nil {
		t.Fatalf("DisableAutoMerge: %v", err)
	}
	if graphQLCalls != 0 {
		t.Errorf("expected no mutation for a PR without auto-merge, got %d calls", graphQLCalls)
	}
}

func TestDisableAutoMerge_postsMutationForAutoMergeRequest(t *testing.T) {
	graphQLCalls := 0
	client := newGitHubStubClient(t, `{"number":7,"node_id":"PR_7","auto_merge":{"merge_method":"squash"}}`, &graphQLCalls)

	if err := client.DisableAutoMerge(context.Background(), 7); err != nil {
		t.Fatalf("DisableAutoMerge: %v", err)
	}
	if graphQLCalls != 1 {
		t.Errorf("expected one mutation for a PR with auto-merge, got %d calls", graphQLCalls)
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

const seedMessage = "chore: seed fixture"

func gitOut(t *testing.T, dir string, args ...string) string {
	t.Helper()
	out, err := exec.Command("git", append([]string{"-C", dir}, args...)...).Output()
	if err != nil {
		t.Fatalf("git %v: %v", args, err)
	}
	return strings.TrimSpace(string(out))
}

func writeAndCommit(t *testing.T, dir, message string, files map[string]string) string {
	t.Helper()
	for name, content := range files {
		if err := os.WriteFile(filepath.Join(dir, name), []byte(content), 0o644); err != nil {
			t.Fatal(err)
		}
		mustRun(t, dir, "git", "add", name)
	}
	mustRun(t, dir, "git", "commit", "-m", message)
	return gitOut(t, dir, "rev-parse", "HEAD")
}

func seededRemote(t *testing.T, files map[string]string) string {
	t.Helper()
	remoteDir := t.TempDir()
	mustRun(t, remoteDir, "git", "init", "--initial-branch=main")
	writeAndCommit(t, remoteDir, seedMessage, files)
	return remoteDir
}

func TestRevertCommit_shallowBoundaryKeepsUnrelatedFiles(t *testing.T) {
	remoteDir := seededRemote(t, map[string]string{"a.yaml": "replicas: 1\n", "b.yaml": "kind: ConfigMap\n"})
	target := writeAndCommit(t, remoteDir, "chore: change replicas", map[string]string{"a.yaml": "replicas: 2\n"})

	c := newTestClient("tok")
	cloneDir, err := c.Clone(context.Background(), remoteDir, "main")
	if err != nil {
		t.Fatalf("Clone: %v", err)
	}
	t.Cleanup(func() { _ = os.RemoveAll(cloneDir) })

	_, err = c.RevertCommit(context.Background(), cloneDir, target, "main", testRevertBranch)
	if err == nil || !strings.Contains(err.Error(), "parent check") {
		t.Errorf("RevertCommit error = %v, want a parent check error", err)
	}
	if gitOut(t, cloneDir, "ls-tree", "--name-only", "HEAD", "b.yaml") == "" {
		t.Errorf("revert of shallow-boundary commit %s deleted b.yaml", target[:7])
	}
}

func TestRevertCommit_conflictLeavesCleanClone(t *testing.T) {
	remoteDir := seededRemote(t, map[string]string{"a.yaml": "replicas: 1\n"})
	target := writeAndCommit(t, remoteDir, "chore: set replicas two", map[string]string{"a.yaml": "replicas: 2\n"})
	writeAndCommit(t, remoteDir, "chore: set replicas three", map[string]string{"a.yaml": "replicas: 3\n"})
	cloneDir := t.TempDir()
	mustRun(t, cloneDir, "git", "clone", remoteDir, ".")

	_, err := newTestClient("tok").RevertCommit(context.Background(), cloneDir, target, "main", testRevertBranch)
	if err == nil {
		t.Fatal("RevertCommit: expected a conflict error")
	}
	if _, statErr := os.Stat(filepath.Join(cloneDir, ".git", "REVERT_HEAD")); statErr == nil {
		t.Errorf("clone left mid-revert after %q", err)
	}
	if status := gitOut(t, cloneDir, "status", "--porcelain"); status != "" {
		t.Errorf("git status --porcelain = %q, want clean", status)
	}
}

const (
	revertStallSeconds = "30"
	markerPollInterval = 10 * time.Millisecond
)

// The wrapper leaves the conflicted revert in place and then blocks, so the request is cancelled mid-step.
const stallingRevertGit = `#!/bin/sh
if [ "$3" = revert ] && [ "$4" = --no-edit ]; then
	"$STALL_REAL_GIT" "$@"
	: > "$STALL_MARKER"
	exec sleep "$STALL_SECONDS"
fi
exec "$STALL_REAL_GIT" "$@"
`

func TestRevertCommit_cancelledRequestLeavesCleanClone(t *testing.T) {
	remoteDir := seededRemote(t, map[string]string{"a.yaml": "replicas: 1\n"})
	target := writeAndCommit(t, remoteDir, "chore: set replicas two", map[string]string{"a.yaml": "replicas: 2\n"})
	writeAndCommit(t, remoteDir, "chore: set replicas three", map[string]string{"a.yaml": "replicas: 3\n"})
	cloneDir := t.TempDir()
	mustRun(t, cloneDir, "git", "clone", remoteDir, ".")

	realGit, err := exec.LookPath("git")
	if err != nil {
		t.Fatal(err)
	}
	binDir := t.TempDir()
	marker := filepath.Join(binDir, "revert-started")
	if err := os.WriteFile(filepath.Join(binDir, "git"), []byte(stallingRevertGit), 0o755); err != nil {
		t.Fatal(err)
	}
	t.Setenv("STALL_REAL_GIT", realGit)
	t.Setenv("STALL_MARKER", marker)
	t.Setenv("STALL_SECONDS", revertStallSeconds)
	t.Setenv("PATH", binDir+string(os.PathListSeparator)+os.Getenv("PATH"))

	ctx, cancel := context.WithCancel(context.Background())
	t.Cleanup(cancel)
	go func() {
		for ctx.Err() == nil {
			if _, statErr := os.Stat(marker); statErr == nil {
				cancel()
				return
			}
			time.Sleep(markerPollInterval)
		}
	}()

	_, err = newTestClient("tok").RevertCommit(ctx, cloneDir, target, "main", testRevertBranch)
	if err == nil || !strings.Contains(err.Error(), revertStepName) {
		t.Fatalf("RevertCommit error = %v, want a %s error", err, revertStepName)
	}
	if _, statErr := os.Stat(filepath.Join(cloneDir, ".git", "REVERT_HEAD")); statErr == nil {
		t.Errorf("clone left mid-revert after a cancelled request: %v", err)
	}
}

func forceResetBase(t *testing.T) (cloneDir, rewritten string) {
	t.Helper()
	remoteDir := seededRemote(t, map[string]string{"a.yaml": "replicas: 1\n"})
	writeAndCommit(t, remoteDir, "chore: set replicas two", map[string]string{"a.yaml": "replicas: 2\n"})

	cloneDir, err := newTestClient("tok").Clone(context.Background(), remoteDir, "main")
	if err != nil {
		t.Fatalf("Clone: %v", err)
	}
	t.Cleanup(func() { _ = os.RemoveAll(cloneDir) })

	mustRun(t, remoteDir, "git", "reset", "--hard", "HEAD~1")
	rewritten = writeAndCommit(t, remoteDir, "chore: reset base fixture", map[string]string{"a.yaml": "replicas: 5\n"})
	return cloneDir, rewritten
}

func TestReadFile_followsForceResetBase(t *testing.T) {
	cloneDir, _ := forceResetBase(t)

	got, err := newTestClient("tok").ReadFile(context.Background(), cloneDir, "main", "a.yaml")
	if err != nil {
		t.Fatalf("ReadFile after force-reset of existing branch main: %v", err)
	}
	if got != "replicas: 5\n" {
		t.Errorf("ReadFile = %q, want the force-reset tip content", got)
	}
}

func TestCreateBranch_followsForceResetBase(t *testing.T) {
	cloneDir, rewritten := forceResetBase(t)

	if err := newTestClient("tok").CreateBranch(context.Background(), cloneDir, "remediation/run-x", "main"); err != nil {
		t.Fatalf("CreateBranch after force-reset of main: %v", err)
	}
	if head := gitOut(t, cloneDir, "rev-parse", "HEAD"); head != rewritten {
		t.Errorf("HEAD = %s, want force-reset tip %s", head, rewritten)
	}
}

func TestReadFile_fetchErrorIsNotBranchNotFound(t *testing.T) {
	remoteDir := seededRemote(t, map[string]string{"a.yaml": "replicas: 1\n"})
	cloneDir, err := newTestClient("tok").Clone(context.Background(), remoteDir, "main")
	if err != nil {
		t.Fatalf("Clone: %v", err)
	}
	t.Cleanup(func() { _ = os.RemoveAll(cloneDir) })
	if err := os.RemoveAll(remoteDir); err != nil {
		t.Fatal(err)
	}

	_, err = newTestClient("tok").ReadFile(context.Background(), cloneDir, "main", "a.yaml")
	if err == nil {
		t.Fatal("ReadFile: expected a fetch error")
	}
	if strings.HasPrefix(err.Error(), "branch not found") {
		t.Errorf("error = %q, want a fetch error", err)
	}
}

func checkRunServer(t *testing.T, runs []map[string]any) *realGitClient {
	t.Helper()
	mux := http.NewServeMux()
	mux.HandleFunc("GET /repos/test/test/pulls/7", func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write([]byte(`{"number":7,"head":{"sha":"` + gateHeadSHA + `"}}`))
	})
	var srvURL string
	mux.HandleFunc("GET /repos/test/test/commits/"+gateHeadSHA+"/check-runs", func(w http.ResponseWriter, r *http.Request) {
		matching := runs
		if name := r.URL.Query().Get("check_name"); name != "" {
			matching = nil
			for _, run := range runs {
				if run["name"] == name {
					matching = append(matching, run)
				}
			}
		}
		page := 1
		_, _ = fmt.Sscan(r.URL.Query().Get("page"), &page)
		lo := min((page-1)*checkRunPageSize, len(matching))
		hi := min(lo+checkRunPageSize, len(matching))
		if hi < len(matching) {
			next := *r.URL
			q := next.Query()
			q.Set("page", fmt.Sprint(page+1))
			next.RawQuery = q.Encode()
			w.Header().Set("Link", fmt.Sprintf(`<%s%s>; rel="next"`, srvURL, next.RequestURI()))
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"total_count": len(matching), "check_runs": matching[lo:hi]})
	})
	srv := httptest.NewServer(mux)
	t.Cleanup(srv.Close)
	srvURL = srv.URL
	gh := gogithub.NewClient(srv.Client())
	baseURL, err := url.Parse(srv.URL + "/")
	if err != nil {
		t.Fatal(err)
	}
	gh.BaseURL = baseURL
	return &realGitClient{gh: gh, owner: "test", repo: "test"}
}

func TestGetCheckRunStatus_findsGateBeyondFirstPage(t *testing.T) {
	runs := make([]map[string]any, 0, checkRunPageSize+1)
	for i := range checkRunPageSize {
		runs = append(runs, map[string]any{"name": fmt.Sprintf("lint-%d", i), "conclusion": "success"})
	}
	runs = append(runs, map[string]any{"name": remediationGateCheckName, "conclusion": "failure"})

	failed, conclusion, headSHA, err := checkRunServer(t, runs).GetCheckRunStatus(context.Background(), 7)
	if err != nil {
		t.Fatalf("GetCheckRunStatus: %v", err)
	}
	if !failed || conclusion != "failure" || headSHA != gateHeadSHA {
		t.Errorf("GetCheckRunStatus = (%v, %q, %q), want (true, \"failure\", %q)", failed, conclusion, headSHA, gateHeadSHA)
	}
}
