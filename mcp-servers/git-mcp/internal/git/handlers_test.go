package git_test

import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/mcptest"
	"github.com/mark3labs/mcp-go/server"

	"github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/auth"
	"github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/config"
	"github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/git"
	gitserver "github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/server"
)

const (
	testMaxBytes         = 4096
	concurrentGoroutines = 100
	testMaxWaitSeconds   = 600
	shortWaitSeconds     = 1
)

type fakeGitClient struct {
	cloneDir            string
	gotBaseBranch       string
	gotBase             string
	gotHead             string
	gotCreateBranchBase string
	mergeableState      string
	commitSHA           string
	prNumber            int
	prState             string
	prMerged            bool
	prMergeSHA          string
	revertSHA           string
	lastRevertBranch    string
	lastRevertHead      string
	pushCalls           int
	err                 error
	getPRCalls          int
	statusCtxErr        error
	mergeCalls          int
	mergeHeadSHA        string
	mergeSHA            string
	mergeErr            error
	mergeDelay          time.Duration
	mergeHasDeadline    bool
	onMerge             func(*fakeGitClient)
	revertDelay         time.Duration
	closePRErr          error
	closePRCalls        int
	deleteBranchErr     error
	deleteBranchCalls   int
	readFileOut         string
	readFileErr         error
	checkRunFailed      bool
	checkRunConclusion  string
	checkRunErr         error
	checkRunHeadSHA     string
}

var _ git.GitClient = &fakeGitClient{}

func (f *fakeGitClient) Clone(_ context.Context, _, baseBranch string) (string, error) {
	f.gotBaseBranch = baseBranch
	return f.cloneDir, f.err
}

func (f *fakeGitClient) CreateBranch(_ context.Context, _, _, baseBranch string) error {
	f.gotCreateBranchBase = baseBranch
	return f.err
}

func (f *fakeGitClient) WriteFile(_ context.Context, _, _, _ string) error {
	return f.err
}

func (f *fakeGitClient) CommitFiles(_ context.Context, _, _, _ string) (string, error) {
	return f.commitSHA, f.err
}

func (f *fakeGitClient) Push(_ context.Context, _, _ string) error {
	f.pushCalls++
	return f.err
}

func (f *fakeGitClient) CreatePR(_ context.Context, _, head, base, _ string) (int, error) {
	f.gotHead = head
	f.gotBase = base
	return f.prNumber, f.err
}

func (f *fakeGitClient) MergePR(ctx context.Context, _ int, headSHA string) (string, error) {
	f.mergeCalls++
	f.mergeHeadSHA = headSHA
	_, f.mergeHasDeadline = ctx.Deadline()
	select {
	case <-time.After(f.mergeDelay):
	case <-ctx.Done():
		return "", ctx.Err()
	}
	if f.onMerge != nil {
		f.onMerge(f)
	}
	return f.mergeSHA, f.mergeErr
}

func (f *fakeGitClient) GetPRStatus(ctx context.Context, _ int) (string, bool, string, error) {
	f.getPRCalls++
	f.statusCtxErr = ctx.Err()
	return f.prState, f.prMerged, f.prMergeSHA, f.err
}

func (f *fakeGitClient) RevertCommit(_ context.Context, _, _, base, head string) (string, error) {
	time.Sleep(f.revertDelay)
	f.lastRevertBranch = base
	f.lastRevertHead = head
	return f.revertSHA, f.err
}

func (f *fakeGitClient) ClosePR(_ context.Context, _ int) error {
	f.closePRCalls++
	return f.closePRErr
}

func (f *fakeGitClient) DeleteBranch(_ context.Context, _ string) error {
	f.deleteBranchCalls++
	return f.deleteBranchErr
}

func (f *fakeGitClient) ReadFile(_ context.Context, _, _, _ string) (string, error) {
	return f.readFileOut, f.readFileErr
}

func (f *fakeGitClient) ResolveManifestPath(_ context.Context, _, _, _, _, _ string) (string, string, error) {
	return f.readFileOut, "", f.readFileErr
}

func (f *fakeGitClient) GetCheckRunStatus(_ context.Context, _ int) (bool, string, string, error) {
	return f.checkRunFailed, f.checkRunConclusion, f.checkRunHeadSHA, f.checkRunErr
}

func (f *fakeGitClient) GetMergeableState(_ context.Context, _ int) (string, error) {
	return f.mergeableState, nil
}

type fakeSessionState struct {
	mu            sync.Mutex
	runID         string
	cloneDir      string
	currentBranch string
	baseBranch    string
	lastCommitSHA string
	prNumber      int
}

var _ git.SessionState = &fakeSessionState{}

func sessionWithPR(prNumber int) *fakeSessionState {
	s := &fakeSessionState{}
	s.SetPRNumber(prNumber)
	return s
}

func (s *fakeSessionState) PRNumber() int {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.prNumber
}

func (s *fakeSessionState) SetPRNumber(prNumber int) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.prNumber = prNumber
}

func (s *fakeSessionState) BeginSession(runID, cloneDir string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.runID = runID
	s.cloneDir = cloneDir
}

func (s *fakeSessionState) Branch() (string, string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.currentBranch, s.cloneDir
}

func (s *fakeSessionState) SetBranch(branch string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.currentBranch = branch
}

func (s *fakeSessionState) BaseBranch() string {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.baseBranch
}

func (s *fakeSessionState) SetBaseBranch(branch string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.baseBranch = branch
}

func (s *fakeSessionState) SetLastCommit(sha string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.lastCommitSHA = sha
}

func (s *fakeSessionState) RunID() string {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.runID
}

func (s *fakeSessionState) CloneDir() string {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.cloneDir
}

func callHandler(t *testing.T, toolName string, tool mcp.Tool, handler server.ToolHandlerFunc, args map[string]any) (*mcp.CallToolResult, error) {
	t.Helper()
	srv, err := mcptest.NewServer(t, server.ServerTool{
		Tool:    tool,
		Handler: handler,
	})
	if err != nil {
		return nil, err
	}
	defer srv.Close()

	var req mcp.CallToolRequest
	req.Params.Name = toolName
	req.Params.Arguments = args
	return srv.Client().CallTool(context.Background(), req)
}

func preloadedState(cloneDir, branch string) *fakeSessionState {
	s := &fakeSessionState{}
	s.BeginSession("run-001", cloneDir)
	s.SetBranch(branch)
	return s
}

func TestCloneRepoHandler_Success(t *testing.T) {
	fake := &fakeGitClient{cloneDir: t.TempDir()}
	state := &fakeSessionState{}
	tool := mcp.NewTool("clone_repo",
		mcp.WithString("run_id", mcp.Required()),
		mcp.WithString("base_branch"),
	)
	handler := git.HandleCloneRepo(fake, state, "https://x-access-token:tok@github.com/x/y.git", testMaxBytes)

	result, err := callHandler(t, "clone_repo", tool, handler, map[string]any{"run_id": "abc123"})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success, got error: %v", result.Content)
	}
	if state.CloneDir() == "" {
		t.Error("expected cloneDir to be set after clone_repo")
	}
}

func TestCloneRepoHandler_Idempotent(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{cloneDir: cloneDir}
	state := preloadedState(cloneDir, "")
	state.SetBaseBranch("main")
	tool := mcp.NewTool("clone_repo",
		mcp.WithString("run_id", mcp.Required()),
		mcp.WithString("base_branch"),
	)
	handler := git.HandleCloneRepo(fake, state, "https://x-access-token:tok@github.com/x/y.git", testMaxBytes)

	result, err := callHandler(t, "clone_repo", tool, handler, map[string]any{"run_id": "abc123"})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success on second call, got error: %v", result.Content)
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "already initialised") {
		t.Errorf("expected 'already initialised', got: %s", text)
	}
}

func TestCloneRepoHandler_DomainError(t *testing.T) {
	fake := &fakeGitClient{err: fmt.Errorf("clone failed")}
	state := &fakeSessionState{}
	tool := mcp.NewTool("clone_repo",
		mcp.WithString("run_id", mcp.Required()),
		mcp.WithString("base_branch"),
	)
	handler := git.HandleCloneRepo(fake, state, "https://x-access-token:tok@github.com/x/y.git", testMaxBytes)

	result, err := callHandler(t, "clone_repo", tool, handler, map[string]any{"run_id": "abc123"})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for clone failure")
	}
}

func TestCloneRepoHandler_MissingRunID(t *testing.T) {
	fake := &fakeGitClient{cloneDir: t.TempDir()}
	state := &fakeSessionState{}
	tool := mcp.NewTool("clone_repo", mcp.WithString("run_id", mcp.Required()))
	handler := git.HandleCloneRepo(fake, state, "", testMaxBytes)

	result, err := callHandler(t, "clone_repo", tool, handler, map[string]any{})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for missing run_id")
	}
}

func TestCloneRepoHandler_RejectsInvalidRunID(t *testing.T) {
	fake := &fakeGitClient{cloneDir: t.TempDir()}
	state := &fakeSessionState{}
	tool := mcp.NewTool("clone_repo", mcp.WithString("run_id", mcp.Required()))
	handler := git.HandleCloneRepo(fake, state, "", testMaxBytes)

	result, err := callHandler(t, "clone_repo", tool, handler, map[string]any{"run_id": "bad;id"})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for invalid run_id")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "run_id") {
		t.Errorf("expected 'run_id' in error message, got: %s", text)
	}
}

func TestCloneRepoHandler_NoTokenInOutput(t *testing.T) {
	const sentinelToken = "SECRET_TOKEN_FIXTURE"
	cfg := &config.Config{
		GitHubToken:    sentinelToken,
		RepoURL:        "https://github.com/x/y.git",
		MaxOutputBytes: testMaxBytes,
	}
	fake := &fakeGitClient{cloneDir: t.TempDir()}
	state := &fakeSessionState{}
	tool := mcp.NewTool("clone_repo",
		mcp.WithString("run_id", mcp.Required()),
		mcp.WithString("base_branch"),
	)
	handler := git.HandleCloneRepo(fake, state, cfg.RepoURL, testMaxBytes)

	result, err := callHandler(t, "clone_repo", tool, handler, map[string]any{"run_id": "run-001"})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success, got error: %v", result.Content)
	}
	text := result.Content[0].(mcp.TextContent).Text
	if strings.Contains(text, sentinelToken) {
		t.Errorf("token sentinel leaked into response: %s", text)
	}
}

func TestCloneRepoHandler_SetsBaseBranchDefault(t *testing.T) {
	fake := &fakeGitClient{cloneDir: t.TempDir()}
	state := &fakeSessionState{}
	tool := mcp.NewTool("clone_repo",
		mcp.WithString("run_id", mcp.Required()),
		mcp.WithString("base_branch"),
	)
	handler := git.HandleCloneRepo(fake, state, "", testMaxBytes)

	result, err := callHandler(t, "clone_repo", tool, handler, map[string]any{"run_id": "abc123"})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success, got error: %v", result.Content)
	}
	if got := state.BaseBranch(); got != "main" {
		t.Errorf("expected baseBranch %q, got %q", "main", got)
	}
}

func TestCloneRepoHandler_SetsBaseBranchExplicit(t *testing.T) {
	fake := &fakeGitClient{cloneDir: t.TempDir()}
	state := &fakeSessionState{}
	tool := mcp.NewTool("clone_repo",
		mcp.WithString("run_id", mcp.Required()),
		mcp.WithString("base_branch"),
	)
	handler := git.HandleCloneRepo(fake, state, "", testMaxBytes)

	result, err := callHandler(t, "clone_repo", tool, handler, map[string]any{
		"run_id":      "abc123",
		"base_branch": "chore/eval-cluster-baseline",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success, got error: %v", result.Content)
	}
	if got := state.BaseBranch(); got != "chore/eval-cluster-baseline" {
		t.Errorf("expected baseBranch %q, got %q", "chore/eval-cluster-baseline", got)
	}
}

func TestCloneRepoHandler_PassesBaseBranchToClone(t *testing.T) {
	fake := &fakeGitClient{cloneDir: t.TempDir()}
	state := &fakeSessionState{}
	tool := mcp.NewTool("clone_repo",
		mcp.WithString("run_id", mcp.Required()),
		mcp.WithString("base_branch"),
	)
	handler := git.HandleCloneRepo(fake, state, "", testMaxBytes)

	_, err := callHandler(t, "clone_repo", tool, handler, map[string]any{
		"run_id":      "abc123",
		"base_branch": "chore/eval-cluster-baseline",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if got := fake.gotBaseBranch; got != "chore/eval-cluster-baseline" {
		t.Errorf("Clone received baseBranch %q, want %q", got, "chore/eval-cluster-baseline")
	}
}

func TestCreateBranchHandler_Success(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{}
	state := preloadedState(cloneDir, "")
	tool := mcp.NewTool("create_branch", mcp.WithString("run_id", mcp.Required()))
	handler := git.HandleCreateBranch(fake, state, testMaxBytes)

	result, err := callHandler(t, "create_branch", tool, handler, map[string]any{"run_id": "abc123"})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success, got error: %v", result.Content)
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "remediation/run-abc123") {
		t.Errorf("expected branch name in response, got: %s", text)
	}
}

func TestCreateBranchHandler_NoSession(t *testing.T) {
	fake := &fakeGitClient{}
	state := &fakeSessionState{}
	tool := mcp.NewTool("create_branch", mcp.WithString("run_id", mcp.Required()))
	handler := git.HandleCreateBranch(fake, state, testMaxBytes)

	result, err := callHandler(t, "create_branch", tool, handler, map[string]any{"run_id": "abc123"})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true when session not initialised")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "clone_repo") {
		t.Errorf("expected 'clone_repo' in error, got: %s", text)
	}
}

func TestCreateBranchHandler_DomainError(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{err: fmt.Errorf("branch create failed")}
	state := preloadedState(cloneDir, "")
	tool := mcp.NewTool("create_branch", mcp.WithString("run_id", mcp.Required()))
	handler := git.HandleCreateBranch(fake, state, testMaxBytes)

	result, err := callHandler(t, "create_branch", tool, handler, map[string]any{"run_id": "abc123"})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for domain error")
	}
}

func TestCreateBranchHandler_MissingArgument(t *testing.T) {
	fake := &fakeGitClient{}
	state := &fakeSessionState{}
	tool := mcp.NewTool("create_branch", mcp.WithString("run_id", mcp.Required()))
	handler := git.HandleCreateBranch(fake, state, testMaxBytes)

	result, err := callHandler(t, "create_branch", tool, handler, map[string]any{})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for missing run_id")
	}
}

func TestCreateBranchHandler_RejectsInvalidRunID(t *testing.T) {
	fake := &fakeGitClient{}
	state := &fakeSessionState{}
	tool := mcp.NewTool("create_branch", mcp.WithString("run_id", mcp.Required()))
	handler := git.HandleCreateBranch(fake, state, testMaxBytes)

	result, err := callHandler(t, "create_branch", tool, handler, map[string]any{"run_id": "bad;branch"})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for invalid run_id")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "run_id") {
		t.Errorf("expected 'run_id' in error message, got: %s", text)
	}
}

func seedManifest(t *testing.T, cloneDir, relPath, body string) {
	t.Helper()
	abs := filepath.Join(cloneDir, relPath)
	if err := os.MkdirAll(filepath.Dir(abs), 0o755); err != nil {
		t.Fatalf("seedManifest mkdir: %v", err)
	}
	if err := os.WriteFile(abs, []byte(body), 0o644); err != nil {
		t.Fatalf("seedManifest write: %v", err)
	}
}

func TestWriteManifestHandler_Success(t *testing.T) {
	cloneDir := t.TempDir()
	seedManifest(t, cloneDir, "apps/deploy.yaml", "apiVersion: v1\nkind: Deployment\n")
	fake := &fakeGitClient{}
	state := preloadedState(cloneDir, "remediation/run-001")
	tool := mcp.NewTool("write_manifest",
		mcp.WithString("manifest_path", mcp.Required()),
		mcp.WithString("patch_body", mcp.Required()),
	)
	handler := git.HandleWriteManifest(fake, state, testMaxBytes)

	result, err := callHandler(t, "write_manifest", tool, handler, map[string]any{
		"manifest_path": "apps/deploy.yaml",
		"patch_body":    "apiVersion: apps/v1\nkind: Deployment\n",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success, got error: %v", result.Content)
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "wrote manifest") {
		t.Errorf("expected confirmation in response, got: %s", text)
	}
}

func TestWriteManifestHandler_DomainError(t *testing.T) {
	cloneDir := t.TempDir()
	seedManifest(t, cloneDir, "apps/deploy.yaml", "apiVersion: v1\n")
	fake := &fakeGitClient{err: fmt.Errorf("write failed")}
	state := preloadedState(cloneDir, "remediation/run-001")
	tool := mcp.NewTool("write_manifest",
		mcp.WithString("manifest_path", mcp.Required()),
		mcp.WithString("patch_body", mcp.Required()),
	)
	handler := git.HandleWriteManifest(fake, state, testMaxBytes)

	result, err := callHandler(t, "write_manifest", tool, handler, map[string]any{
		"manifest_path": "apps/deploy.yaml",
		"patch_body":    "content",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for domain error")
	}
}

func TestWriteManifestHandler_RejectsMissingPath(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{}
	state := preloadedState(cloneDir, "remediation/run-001")
	tool := mcp.NewTool("write_manifest",
		mcp.WithString("manifest_path", mcp.Required()),
		mcp.WithString("patch_body", mcp.Required()),
	)
	handler := git.HandleWriteManifest(fake, state, testMaxBytes)

	result, err := callHandler(t, "write_manifest", tool, handler, map[string]any{
		"manifest_path": "apps/does-not-exist.yaml",
		"patch_body":    "apiVersion: v1\n",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for missing path")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "does not exist") {
		t.Errorf("expected 'does not exist' in error, got: %s", text)
	}
}

func TestWriteManifestHandler_RejectsNoOpPatch(t *testing.T) {
	cloneDir := t.TempDir()
	body := "apiVersion: v1\nkind: Deployment\n"
	seedManifest(t, cloneDir, "apps/deploy.yaml", body)
	fake := &fakeGitClient{}
	state := preloadedState(cloneDir, "remediation/run-001")
	tool := mcp.NewTool("write_manifest",
		mcp.WithString("manifest_path", mcp.Required()),
		mcp.WithString("patch_body", mcp.Required()),
	)
	handler := git.HandleWriteManifest(fake, state, testMaxBytes)

	result, err := callHandler(t, "write_manifest", tool, handler, map[string]any{
		"manifest_path": "apps/deploy.yaml",
		"patch_body":    body,
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for no-op patch")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "no-op") {
		t.Errorf("expected 'no-op' in error, got: %s", text)
	}
}

func TestWriteManifestHandler_RejectsRuntimeOnlyFields(t *testing.T) {
	cases := []struct {
		name        string
		patchBody   string
		wantInError string
	}{
		{
			name:        "creationTimestamp",
			patchBody:   "apiVersion: v1\nkind: Deployment\nmetadata:\n  creationTimestamp: \"2026-05-20T10:00:00Z\"\n  name: foo\n",
			wantInError: "metadata.creationTimestamp",
		},
		{
			name:        "resourceVersion",
			patchBody:   "apiVersion: v1\nkind: Deployment\nmetadata:\n  resourceVersion: \"12345\"\n  name: foo\n",
			wantInError: "metadata.resourceVersion",
		},
		{
			name:        "uid",
			patchBody:   "apiVersion: v1\nkind: Deployment\nmetadata:\n  uid: abc-def\n  name: foo\n",
			wantInError: "metadata.uid",
		},
		{
			name:        "generation",
			patchBody:   "apiVersion: v1\nkind: Deployment\nmetadata:\n  generation: 3\n  name: foo\n",
			wantInError: "metadata.generation",
		},
		{
			name:        "managedFields",
			patchBody:   "apiVersion: v1\nkind: Deployment\nmetadata:\n  managedFields:\n  - manager: kubectl\n  name: foo\n",
			wantInError: "metadata.managedFields",
		},
		{
			name:        "top-level status",
			patchBody:   "apiVersion: v1\nkind: Deployment\nmetadata:\n  name: foo\nstatus:\n  replicas: 3\n",
			wantInError: "status",
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			cloneDir := t.TempDir()
			seedManifest(t, cloneDir, "apps/deploy.yaml", "apiVersion: v1\nkind: Deployment\nmetadata:\n  name: foo\n")
			fake := &fakeGitClient{}
			state := preloadedState(cloneDir, "remediation/run-001")
			tool := mcp.NewTool("write_manifest",
				mcp.WithString("manifest_path", mcp.Required()),
				mcp.WithString("patch_body", mcp.Required()),
			)
			handler := git.HandleWriteManifest(fake, state, testMaxBytes)

			result, err := callHandler(t, "write_manifest", tool, handler, map[string]any{
				"manifest_path": "apps/deploy.yaml",
				"patch_body":    tc.patchBody,
			})
			if err != nil {
				t.Fatalf("CallTool error: %v", err)
			}
			if !result.IsError {
				t.Errorf("expected IsError=true for runtime-only field %s", tc.name)
			}
			text := result.Content[0].(mcp.TextContent).Text
			if !strings.Contains(text, tc.wantInError) {
				t.Errorf("expected %q in error, got: %s", tc.wantInError, text)
			}
		})
	}
}

func TestWriteManifestHandler_RejectsPathTraversal(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{}
	state := preloadedState(cloneDir, "remediation/run-001")
	tool := mcp.NewTool("write_manifest",
		mcp.WithString("manifest_path", mcp.Required()),
		mcp.WithString("patch_body", mcp.Required()),
	)
	handler := git.HandleWriteManifest(fake, state, testMaxBytes)

	result, err := callHandler(t, "write_manifest", tool, handler, map[string]any{
		"manifest_path": "../../etc/passwd",
		"patch_body":    "malicious",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for path traversal")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "manifest_path") {
		t.Errorf("expected 'manifest_path' in error message, got: %s", text)
	}
}

func TestWriteManifestHandler_RejectsAbsolutePath(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{}
	state := preloadedState(cloneDir, "remediation/run-001")
	tool := mcp.NewTool("write_manifest",
		mcp.WithString("manifest_path", mcp.Required()),
		mcp.WithString("patch_body", mcp.Required()),
	)
	handler := git.HandleWriteManifest(fake, state, testMaxBytes)

	result, err := callHandler(t, "write_manifest", tool, handler, map[string]any{
		"manifest_path": "/etc/passwd",
		"patch_body":    "malicious",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for absolute path")
	}
}

func TestWriteManifestHandler_RejectsInvalidYAML(t *testing.T) {
	cloneDir := t.TempDir()
	seedManifest(t, cloneDir, "apps/deploy.yaml", "apiVersion: v1\nkind: Deployment\n")
	fake := &fakeGitClient{}
	state := preloadedState(cloneDir, "remediation/run-001")
	tool := mcp.NewTool("write_manifest",
		mcp.WithString("manifest_path", mcp.Required()),
		mcp.WithString("patch_body", mcp.Required()),
	)
	handler := git.HandleWriteManifest(fake, state, testMaxBytes)

	result, err := callHandler(t, "write_manifest", tool, handler, map[string]any{
		"manifest_path": "apps/deploy.yaml",
		"patch_body":    `apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: vigil-app\n`,
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for literal-escape YAML")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "yaml parse error") {
		t.Errorf("expected 'yaml parse error' in error, got: %s", text)
	}
}

func TestWriteManifestHandler_AcceptsValidYAML(t *testing.T) {
	cloneDir := t.TempDir()
	seedManifest(t, cloneDir, "apps/deploy.yaml", "apiVersion: v1\nkind: Deployment\n")
	fake := &fakeGitClient{}
	state := preloadedState(cloneDir, "remediation/run-001")
	tool := mcp.NewTool("write_manifest",
		mcp.WithString("manifest_path", mcp.Required()),
		mcp.WithString("patch_body", mcp.Required()),
	)
	handler := git.HandleWriteManifest(fake, state, testMaxBytes)

	result, err := callHandler(t, "write_manifest", tool, handler, map[string]any{
		"manifest_path": "apps/deploy.yaml",
		"patch_body":    "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: vigil-app\n",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success for valid YAML, got error: %v", result.Content)
	}
}

func TestWriteManifestHandler_RejectsNonIntegerReplicas(t *testing.T) {
	cloneDir := t.TempDir()
	seedManifest(t, cloneDir, "apps/deploy.yaml", "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: vigil-app\nspec:\n  replicas: 1\n")
	fake := &fakeGitClient{}
	state := preloadedState(cloneDir, "remediation/run-001")
	tool := mcp.NewTool("write_manifest",
		mcp.WithString("manifest_path", mcp.Required()),
		mcp.WithString("patch_body", mcp.Required()),
	)
	handler := git.HandleWriteManifest(fake, state, testMaxBytes)

	result, err := callHandler(t, "write_manifest", tool, handler, map[string]any{
		"manifest_path": "apps/deploy.yaml",
		"patch_body":    "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: vigil-app\nspec:\n  replicas: IQ\n",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for non-integer replicas")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "schema error") {
		t.Errorf("expected 'schema error' in error, got: %s", text)
	}
	if !strings.Contains(text, "replicas") {
		t.Errorf("expected offending field 'replicas' in error, got: %s", text)
	}
}

func TestWriteManifestHandler_AcceptsValidTypedManifest(t *testing.T) {
	cloneDir := t.TempDir()
	seedManifest(t, cloneDir, "apps/deploy.yaml", "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: vigil-app\nspec:\n  replicas: 1\n")
	fake := &fakeGitClient{}
	state := preloadedState(cloneDir, "remediation/run-001")
	tool := mcp.NewTool("write_manifest",
		mcp.WithString("manifest_path", mcp.Required()),
		mcp.WithString("patch_body", mcp.Required()),
	)
	handler := git.HandleWriteManifest(fake, state, testMaxBytes)

	result, err := callHandler(t, "write_manifest", tool, handler, map[string]any{
		"manifest_path": "apps/deploy.yaml",
		"patch_body":    "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: vigil-app\nspec:\n  replicas: 3\n",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success for valid typed manifest, got error: %v", result.Content)
	}
}

func TestWriteManifestHandler_AcceptsUnregisteredKind(t *testing.T) {
	cloneDir := t.TempDir()
	seedManifest(t, cloneDir, "apps/kustomization.yaml", "apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\nresources:\n- deploy.yaml\n")
	fake := &fakeGitClient{}
	state := preloadedState(cloneDir, "remediation/run-001")
	tool := mcp.NewTool("write_manifest",
		mcp.WithString("manifest_path", mcp.Required()),
		mcp.WithString("patch_body", mcp.Required()),
	)
	handler := git.HandleWriteManifest(fake, state, testMaxBytes)

	result, err := callHandler(t, "write_manifest", tool, handler, map[string]any{
		"manifest_path": "apps/kustomization.yaml",
		"patch_body":    "apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\nresources:\n- deploy.yaml\n- service.yaml\n",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success for unregistered kind, got error: %v", result.Content)
	}
}

func TestCommitFilesHandler_Success(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{commitSHA: "abc1234"}
	state := preloadedState(cloneDir, "remediation/run-001")
	tool := mcp.NewTool("commit_files", mcp.WithString("message", mcp.Required()))
	handler := git.HandleCommitFiles(fake, state)

	result, err := callHandler(t, "commit_files", tool, handler, map[string]any{"message": "fix: reduce replicas"})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success, got error: %v", result.Content)
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "abc1234") {
		t.Errorf("expected commit SHA in response, got: %s", text)
	}
}

func TestCommitFilesHandler_DomainError(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{err: fmt.Errorf("nothing to commit")}
	state := preloadedState(cloneDir, "remediation/run-001")
	tool := mcp.NewTool("commit_files", mcp.WithString("message", mcp.Required()))
	handler := git.HandleCommitFiles(fake, state)

	result, err := callHandler(t, "commit_files", tool, handler, map[string]any{"message": "fix: reduce replicas"})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for domain error")
	}
}

func TestCommitFilesHandler_MissingArgument(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{}
	state := preloadedState(cloneDir, "remediation/run-001")
	tool := mcp.NewTool("commit_files", mcp.WithString("message", mcp.Required()))
	handler := git.HandleCommitFiles(fake, state)

	result, err := callHandler(t, "commit_files", tool, handler, map[string]any{})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for missing message")
	}
}

func TestPushBranchHandler_Success(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{}
	state := preloadedState(cloneDir, "remediation/run-001")
	tool := mcp.NewTool("push_branch")
	handler := git.HandlePushBranch(fake, state, git.ProtectedBranches{}, testMaxBytes)

	result, err := callHandler(t, "push_branch", tool, handler, map[string]any{})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success, got error: %v", result.Content)
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "pushed") {
		t.Errorf("expected 'pushed' in response, got: %s", text)
	}
}

func TestPushBranchHandler_DomainError(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{err: fmt.Errorf("push rejected")}
	state := preloadedState(cloneDir, "remediation/run-001")
	tool := mcp.NewTool("push_branch")
	handler := git.HandlePushBranch(fake, state, git.ProtectedBranches{}, testMaxBytes)

	result, err := callHandler(t, "push_branch", tool, handler, map[string]any{})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for domain error")
	}
}

func TestPushBranchHandler_NoSession(t *testing.T) {
	fake := &fakeGitClient{}
	state := &fakeSessionState{}
	tool := mcp.NewTool("push_branch")
	handler := git.HandlePushBranch(fake, state, git.ProtectedBranches{}, testMaxBytes)

	result, err := callHandler(t, "push_branch", tool, handler, map[string]any{})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true when session not initialised")
	}
}

func TestCreatePRHandler_Success(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{prNumber: 42}
	state := preloadedState(cloneDir, "remediation/run-001")
	state.SetBaseBranch("main")
	tool := mcp.NewTool("create_pr",
		mcp.WithString("title", mcp.Required()),
		mcp.WithString("body", mcp.Required()),
	)
	handler := git.HandleCreatePR(fake, state)

	result, err := callHandler(t, "create_pr", tool, handler, map[string]any{
		"title": "fix: reduce OOMKilled replicas",
		"body":  "Automated remediation",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success, got error: %v", result.Content)
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "#42") {
		t.Errorf("expected PR number in response, got: %s", text)
	}
}

func TestCreatePR_neverMergesAndIgnoresAutoMergeArgument(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{prNumber: 42, prState: "open", checkRunConclusion: "success", checkRunHeadSHA: "abc123"}
	state := preloadedState(cloneDir, "remediation/run-001")
	state.SetBaseBranch("main")
	tool := mcp.NewTool("create_pr",
		mcp.WithString("title", mcp.Required()),
		mcp.WithString("body", mcp.Required()),
	)
	handler := git.HandleCreatePR(fake, state)

	result, err := callHandler(t, "create_pr", tool, handler, map[string]any{
		"title":      "fix: reduce OOMKilled replicas",
		"body":       "Automated remediation",
		"auto_merge": true,
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError || !strings.Contains(resultText(result), "#42") {
		t.Errorf("expected PR #42 created, got: %v", result.Content)
	}
	if fake.mergeCalls != 0 {
		t.Errorf("create_pr merged the PR %d times, want 0", fake.mergeCalls)
	}
}

func TestCreatePRHandler_UsesSessionBaseBranch(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{prNumber: 7}
	state := preloadedState(cloneDir, "remediation/run-001")
	state.SetBaseBranch("chore/eval-cluster-baseline")
	tool := mcp.NewTool("create_pr",
		mcp.WithString("title", mcp.Required()),
		mcp.WithString("body", mcp.Required()),
	)
	handler := git.HandleCreatePR(fake, state)

	_, err := callHandler(t, "create_pr", tool, handler, map[string]any{
		"title": "fix: bad image tag",
		"body":  "Automated remediation",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if got := fake.gotBase; got != "chore/eval-cluster-baseline" {
		t.Errorf("CreatePR received base %q, want %q", got, "chore/eval-cluster-baseline")
	}
}

func TestCreatePRHandler_FailsWhenBaseBranchUnset(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{prNumber: 1}
	state := preloadedState(cloneDir, "remediation/run-001")
	tool := mcp.NewTool("create_pr",
		mcp.WithString("title", mcp.Required()),
		mcp.WithString("body", mcp.Required()),
	)
	handler := git.HandleCreatePR(fake, state)

	result, err := callHandler(t, "create_pr", tool, handler, map[string]any{
		"title": "fix: bad image tag",
		"body":  "Automated remediation",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true when base branch is unset in session")
	}
}

func TestCreatePRHandler_DomainError(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{err: fmt.Errorf("API error")}
	state := preloadedState(cloneDir, "remediation/run-001")
	state.SetBaseBranch("main")
	tool := mcp.NewTool("create_pr",
		mcp.WithString("title", mcp.Required()),
		mcp.WithString("body", mcp.Required()),
	)
	handler := git.HandleCreatePR(fake, state)

	result, err := callHandler(t, "create_pr", tool, handler, map[string]any{
		"title": "fix: reduce replicas",
		"body":  "Remediation",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for domain error")
	}
}

func TestCreatePRHandler_MissingArgument(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{}
	state := preloadedState(cloneDir, "remediation/run-001")
	state.SetBaseBranch("main")
	tool := mcp.NewTool("create_pr",
		mcp.WithString("title", mcp.Required()),
		mcp.WithString("body", mcp.Required()),
	)
	handler := git.HandleCreatePR(fake, state)

	result, err := callHandler(t, "create_pr", tool, handler, map[string]any{"title": "t"})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for missing body")
	}
}

func TestGetPRStatusHandler_Success(t *testing.T) {
	fake := &fakeGitClient{prState: "open", prMerged: false, prMergeSHA: ""}
	state := &fakeSessionState{}
	tool := mcp.NewTool("get_pr_status", mcp.WithNumber("pr_number", mcp.Required()))
	handler := git.HandleGetPRStatus(fake, state)

	result, err := callHandler(t, "get_pr_status", tool, handler, map[string]any{"pr_number": float64(42)})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success, got error: %v", result.Content)
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "open") {
		t.Errorf("expected state in response, got: %s", text)
	}
}

func TestGetPRStatusHandler_DomainError(t *testing.T) {
	fake := &fakeGitClient{err: fmt.Errorf("rate limited")}
	state := &fakeSessionState{}
	tool := mcp.NewTool("get_pr_status", mcp.WithNumber("pr_number", mcp.Required()))
	handler := git.HandleGetPRStatus(fake, state)

	result, err := callHandler(t, "get_pr_status", tool, handler, map[string]any{"pr_number": float64(42)})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for domain error")
	}
}

func TestGetPRStatusHandler_MissingArgument(t *testing.T) {
	fake := &fakeGitClient{}
	state := &fakeSessionState{}
	tool := mcp.NewTool("get_pr_status", mcp.WithNumber("pr_number", mcp.Required()))
	handler := git.HandleGetPRStatus(fake, state)

	result, err := callHandler(t, "get_pr_status", tool, handler, map[string]any{})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for missing pr_number")
	}
}

func TestWaitForGateHandler_Success(t *testing.T) {
	fake := &fakeGitClient{prState: "open", prMerged: true, prMergeSHA: "deadbeef"}

	result := runWaitForGate(t, fake, testMaxWaitSeconds)

	if result.IsError {
		t.Errorf("expected success (merged), got error: %v", result.Content)
	}
	if text := resultText(result); !strings.Contains(text, "gate passed") {
		t.Errorf("expected gate passed in response, got: %s", text)
	}
}

func TestWaitForGateHandler_DomainError(t *testing.T) {
	fake := &fakeGitClient{err: fmt.Errorf("API unreachable")}

	result := runWaitForGate(t, fake, shortWaitSeconds)

	if !result.IsError {
		t.Error("expected IsError=true when every poll errors")
	}
	if text := resultText(result); !strings.Contains(text, "gate wait ended after 1 seconds") {
		t.Errorf("expected the wait to run to its deadline, got: %s", text)
	}
}

func TestWaitForGate_ignoresTimeoutArgument(t *testing.T) {
	const budgetSeconds = 2
	fake := &fakeGitClient{prState: "open"}
	handler := git.HandleWaitForGate(fake, sessionWithPR(42), time.Millisecond, budgetSeconds)

	start := time.Now()
	result, err := callHandler(t, "wait_for_gate", waitForGateTool(), handler, map[string]any{
		"pr_number":       float64(42),
		"timeout_seconds": float64(1),
	})
	elapsed := time.Since(start)

	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if elapsed < budgetSeconds*time.Second {
		t.Errorf("wait ended after %v, want the full %ds budget", elapsed, budgetSeconds)
	}
	if text := resultText(result); !result.IsError || !strings.Contains(text, "gate wait ended after 2 seconds") {
		t.Errorf("unexpected end state: %s", text)
	}
}

func TestWaitForGateHandler_MissingArgument(t *testing.T) {
	fake := &fakeGitClient{}
	state := &fakeSessionState{}
	handler := git.HandleWaitForGate(fake, state, time.Millisecond, testMaxWaitSeconds)

	result, err := callHandler(t, "wait_for_gate", waitForGateTool(), handler, map[string]any{})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for missing pr_number")
	}
}

func TestWaitForGateHandler_GateCheckFailed(t *testing.T) {
	fake := &fakeGitClient{
		prState:            "open",
		prMerged:           false,
		checkRunFailed:     true,
		checkRunConclusion: "failure",
	}

	result := runWaitForGate(t, fake, testMaxWaitSeconds)

	if !result.IsError {
		t.Error("expected IsError=true when gate check failed")
	}
	text := resultText(result)
	if !strings.Contains(text, "gate check failed") {
		t.Errorf("expected 'gate check failed' in error, got: %s", text)
	}
	if !strings.Contains(text, "failure") {
		t.Errorf("expected conclusion in error, got: %s", text)
	}
}

func TestWaitForGateHandler_FailsFastWhenUnmergeableAndUngated(t *testing.T) {
	fake := &fakeGitClient{
		prState:        "open",
		prMerged:       false,
		mergeableState: "dirty",
	}

	result := runWaitForGate(t, fake, testMaxWaitSeconds)

	if !result.IsError {
		t.Error("expected IsError=true for unmergeable, ungated PR")
	}
	text := resultText(result)
	if !strings.Contains(text, "unmergeable") {
		t.Errorf("expected 'unmergeable' in error, got: %s", text)
	}
}

func TestWaitForGateHandler_DirtyButGatedDoesNotFailFast(t *testing.T) {
	fake := &fakeGitClient{
		prState:            "open",
		prMerged:           false,
		mergeableState:     "dirty",
		checkRunConclusion: "success",
		checkRunHeadSHA:    "abc123",
		mergeErr:           errors.New("merge_pr #42: 405 Pull Request is not mergeable"),
	}

	result := runWaitForGate(t, fake, shortWaitSeconds)

	if !result.IsError {
		t.Error("expected IsError=true (timeout), got success")
	}
	if text := resultText(result); !strings.Contains(text, "gate wait ended after 1 seconds") {
		t.Errorf("expected gate wait end error when gate present, got: %s", text)
	}
}

func waitForGateTool() mcp.Tool {
	return mcp.NewTool("wait_for_gate", mcp.WithNumber("pr_number", mcp.Required()))
}

func runWaitForGateEvery(t *testing.T, client git.GitClient, maxWaitSeconds int, pollInterval time.Duration) *mcp.CallToolResult {
	t.Helper()
	handler := git.HandleWaitForGate(client, sessionWithPR(42), pollInterval, maxWaitSeconds)
	result, err := callHandler(t, "wait_for_gate", waitForGateTool(), handler, map[string]any{"pr_number": float64(42)})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	return result
}

func runWaitForGate(t *testing.T, client git.GitClient, maxWaitSeconds int) *mcp.CallToolResult {
	t.Helper()
	return runWaitForGateEvery(t, client, maxWaitSeconds, time.Millisecond)
}

func runFinalReadOnly(t *testing.T, client git.GitClient) *mcp.CallToolResult {
	t.Helper()
	return runWaitForGateEvery(t, client, shortWaitSeconds, time.Hour)
}

func resultText(result *mcp.CallToolResult) string {
	return result.Content[0].(mcp.TextContent).Text
}

func TestWaitForGateHandler_TimeoutRereadsState(t *testing.T) {
	fake := &fakeGitClient{prState: "open"}

	result := runFinalReadOnly(t, fake)

	if !result.IsError {
		t.Fatal("expected IsError=true when the wait ends without a merge")
	}
	if fake.getPRCalls != 1 {
		t.Errorf("expected one final PR status read, got %d", fake.getPRCalls)
	}
	if text := resultText(result); !strings.Contains(text, "gate wait ended after 1 seconds; PR #42 open and not merged") {
		t.Errorf("unexpected end state: %s", text)
	}
}

func TestWaitForGateHandler_MergeSeenInFinalReadSucceeds(t *testing.T) {
	fake := &fakeGitClient{prState: "closed", prMerged: true, prMergeSHA: "1a7e5ha"}

	result := runFinalReadOnly(t, fake)

	if result.IsError {
		t.Fatalf("expected success for a merge seen in the final read, got: %s", resultText(result))
	}
	if structured, ok := result.StructuredContent.(map[string]any); !ok || structured["merge_commit_sha"] != "1a7e5ha" {
		t.Errorf("structured result = %#v, want merge_commit_sha 1a7e5ha", result.StructuredContent)
	}
}

func TestWaitForGateHandler_GateFailureRereadsState(t *testing.T) {
	fake := &fakeGitClient{prState: "open", checkRunFailed: true, checkRunConclusion: "cancelled"}

	result := runWaitForGate(t, fake, testMaxWaitSeconds)

	if !result.IsError {
		t.Fatal("expected IsError=true when the gate fails")
	}
	if fake.getPRCalls != 2 {
		t.Errorf("expected one poll and one final PR status read, got %d reads", fake.getPRCalls)
	}
	if text := resultText(result); !strings.Contains(text, "(gate check failed (conclusion=cancelled)); PR #42 open and not merged") {
		t.Errorf("unexpected end state: %s", text)
	}
}

func TestWaitForGateHandler_ClosedWithoutMergeReportsFinalState(t *testing.T) {
	fake := &fakeGitClient{prState: "closed"}

	result := runWaitForGate(t, fake, testMaxWaitSeconds)

	if !result.IsError {
		t.Fatal("expected IsError=true for a PR closed without merge")
	}
	if fake.getPRCalls != 2 {
		t.Errorf("expected one poll and one final PR status read, got %d reads", fake.getPRCalls)
	}
	if text := resultText(result); !strings.Contains(text, "(PR closed without merge); PR #42 closed and not merged") {
		t.Errorf("unexpected end state: %s", text)
	}
}

func TestWaitForGateHandler_FinalReadFailureNamesUnknownState(t *testing.T) {
	fake := &fakeGitClient{prState: "open", err: errors.New("api down")}

	result := runFinalReadOnly(t, fake)

	if !result.IsError {
		t.Fatal("expected IsError=true when the final state cannot be read")
	}
	if text := resultText(result); !strings.Contains(text, "final state of PR #42 could not be read (api down)") {
		t.Errorf("unexpected end state: %s", text)
	}
}

func TestWaitForGateHandler_CancelledRequestStillFinalises(t *testing.T) {
	fake := &fakeGitClient{prState: "open"}
	handler := git.HandleWaitForGate(fake, sessionWithPR(42), time.Hour, testMaxWaitSeconds)
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	var req mcp.CallToolRequest
	req.Params.Name = "wait_for_gate"
	req.Params.Arguments = map[string]any{"pr_number": float64(42)}

	result, err := handler(ctx, req)

	if err != nil {
		t.Fatalf("handler error: %v", err)
	}
	if fake.getPRCalls != 1 || fake.statusCtxErr != nil {
		t.Errorf("expected one final PR status read on a live context, got %d reads, ctx err %v", fake.getPRCalls, fake.statusCtxErr)
	}
	if text := resultText(result); !strings.Contains(text, "; PR #42 open and not merged") {
		t.Errorf("unexpected end state: %s", text)
	}
}

func revertCommitTool() mcp.Tool {
	return mcp.NewTool("revert_commit", mcp.WithString("merge_commit_sha", mcp.Required()))
}

func mergedRevertClient() *fakeGitClient {
	return &fakeGitClient{revertSHA: "cafebabe", prNumber: 7, prMerged: true, prMergeSHA: "f00dfeed"}
}

func TestRevertCommitHandler_Success(t *testing.T) {
	fake := mergedRevertClient()
	state := preloadedState(t.TempDir(), "remediation/run-001")
	state.SetBaseBranch("main")
	handler := git.HandleRevertCommit(fake, state, git.ProtectedBranches{}, time.Millisecond, testMaxWaitSeconds)

	result, err := callHandler(t, "revert_commit", revertCommitTool(), handler, map[string]any{
		"merge_commit_sha": "deadbeef",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Fatalf("expected success, got error: %v", result.Content)
	}
	structured, ok := result.StructuredContent.(map[string]any)
	if !ok || structured["sha"] != "cafebabe" || structured["pr_number"] != float64(7) || structured["merge_commit_sha"] != "f00dfeed" {
		t.Errorf("structured result = %#v, want sha cafebabe, pr_number 7, merge_commit_sha f00dfeed", result.StructuredContent)
	}
	if fake.lastRevertBranch != "main" || fake.lastRevertHead != "remediation/revert-deadbeef" {
		t.Errorf("RevertCommit base/head = %q/%q, want main/remediation/revert-deadbeef", fake.lastRevertBranch, fake.lastRevertHead)
	}
	if fake.gotHead != "remediation/revert-deadbeef" || fake.gotBase != "main" {
		t.Errorf("CreatePR head/base = %q/%q, want remediation/revert-deadbeef/main", fake.gotHead, fake.gotBase)
	}
	if fake.mergeCalls != 0 {
		t.Errorf("expected no merge call for an already merged revert PR, got %d", fake.mergeCalls)
	}
}

func TestRevertCommit_mergesRevertThroughGate(t *testing.T) {
	fake := &fakeGitClient{revertSHA: "cafebabe", prNumber: 7, prState: "open", checkRunConclusion: "success", checkRunHeadSHA: "abc123", mergeSHA: "f00dfeed"}
	state := preloadedState(t.TempDir(), "remediation/run-001")
	state.SetBaseBranch("main")
	handler := git.HandleRevertCommit(fake, state, git.ProtectedBranches{}, time.Millisecond, testMaxWaitSeconds)

	result, err := callHandler(t, "revert_commit", revertCommitTool(), handler, map[string]any{"merge_commit_sha": "deadbeef"})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Fatalf("expected the revert PR merged through the gate, got: %s", resultText(result))
	}
	if fake.mergeCalls != 1 || fake.mergeHeadSHA != "abc123" {
		t.Errorf("MergePR calls = %d with head %q, want 1 with abc123", fake.mergeCalls, fake.mergeHeadSHA)
	}
	if structured, ok := result.StructuredContent.(map[string]any); !ok || structured["merge_commit_sha"] != "f00dfeed" {
		t.Errorf("structured result = %#v, want merge_commit_sha f00dfeed", result.StructuredContent)
	}
}

func TestRevertCommitHandler_BranchNameUsesShortSHA(t *testing.T) {
	fake := mergedRevertClient()
	state := preloadedState(t.TempDir(), "remediation/run-001")
	state.SetBaseBranch("main")
	handler := git.HandleRevertCommit(fake, state, git.ProtectedBranches{}, time.Millisecond, testMaxWaitSeconds)

	result, err := callHandler(t, "revert_commit", revertCommitTool(), handler, map[string]any{
		"merge_commit_sha": "0123456789abcdef0123456789abcdef01234567",
	})
	if err != nil || result.IsError {
		t.Fatalf("revert_commit: %v %v", err, result)
	}
	if want := "remediation/revert-0123456789ab"; fake.lastRevertHead != want || fake.gotHead != want {
		t.Errorf("revert branch = %q (pr head %q), want %q", fake.lastRevertHead, fake.gotHead, want)
	}
}

func TestRevertCommitHandler_GateFailureReturnsError(t *testing.T) {
	fake := &fakeGitClient{revertSHA: "cafebabe", prNumber: 7, prState: "open", checkRunFailed: true, checkRunConclusion: "failure"}
	state := preloadedState(t.TempDir(), "remediation/run-001")
	state.SetBaseBranch("main")
	handler := git.HandleRevertCommit(fake, state, git.ProtectedBranches{}, time.Millisecond, testMaxWaitSeconds)

	result, err := callHandler(t, "revert_commit", revertCommitTool(), handler, map[string]any{
		"merge_commit_sha": "deadbeef",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Fatal("expected IsError=true when the gate fails")
	}
	if text := result.Content[0].(mcp.TextContent).Text; !strings.Contains(text, "gate check failed") || !strings.Contains(text, "#7") {
		t.Errorf("expected gate failure naming PR #7, got: %s", text)
	}
	if fake.mergeCalls != 0 {
		t.Errorf("expected no merge after the gate failed, got %d", fake.mergeCalls)
	}
}

func TestRevertCommitHandler_TimeoutReturnsError(t *testing.T) {
	fake := &fakeGitClient{revertSHA: "cafebabe", prNumber: 7, prState: "open"}
	state := preloadedState(t.TempDir(), "remediation/run-001")
	state.SetBaseBranch("main")
	handler := git.HandleRevertCommit(fake, state, git.ProtectedBranches{}, time.Millisecond, shortWaitSeconds)

	result, err := callHandler(t, "revert_commit", revertCommitTool(), handler, map[string]any{
		"merge_commit_sha": "deadbeef",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Fatal("expected IsError=true on timeout")
	}
	if text := result.Content[0].(mcp.TextContent).Text; !strings.Contains(text, "revert PR #7: gate wait ended after 1 seconds; PR #7 open and not merged") {
		t.Errorf("expected gate wait end error, got: %s", text)
	}
}

func TestRevertCommitHandler_GateDeadlineCountsFromHandlerEntry(t *testing.T) {
	const setupDelay = 900 * time.Millisecond
	const maxWall = 1500 * time.Millisecond
	fake := &fakeGitClient{revertSHA: "cafebabe", prNumber: 7, prState: "open", revertDelay: setupDelay}
	state := preloadedState(t.TempDir(), "remediation/run-001")
	state.SetBaseBranch("main")
	handler := git.HandleRevertCommit(fake, state, git.ProtectedBranches{}, time.Hour, shortWaitSeconds)

	start := time.Now()
	result, err := callHandler(t, "revert_commit", revertCommitTool(), handler, map[string]any{
		"merge_commit_sha": "deadbeef",
	})
	elapsed := time.Since(start)

	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if elapsed > maxWall {
		t.Errorf("revert_commit took %v, want the gate deadline one second after entry", elapsed)
	}
	if fake.getPRCalls != 1 {
		t.Errorf("expected one final PR status read, got %d", fake.getPRCalls)
	}
	if text := resultText(result); !strings.Contains(text, "revert PR #7: gate wait ended after 1 seconds; PR #7 open and not merged") {
		t.Errorf("unexpected end state: %s", text)
	}
}

func TestRevertCommitHandler_MergeSeenInFinalReadSucceeds(t *testing.T) {
	fake := &fakeGitClient{revertSHA: "cafebabe", prNumber: 7, prState: "closed", prMerged: true, prMergeSHA: "1a7e5ha"}
	state := preloadedState(t.TempDir(), "remediation/run-001")
	state.SetBaseBranch("main")
	handler := git.HandleRevertCommit(fake, state, git.ProtectedBranches{}, time.Hour, shortWaitSeconds)

	result, err := callHandler(t, "revert_commit", revertCommitTool(), handler, map[string]any{
		"merge_commit_sha": "deadbeef",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Fatalf("expected success for a merge seen in the final read, got: %s", resultText(result))
	}
	if structured, ok := result.StructuredContent.(map[string]any); !ok || structured["merge_commit_sha"] != "1a7e5ha" {
		t.Errorf("structured result = %#v, want merge_commit_sha 1a7e5ha", result.StructuredContent)
	}
}

func TestRevertCommitHandler_DomainError(t *testing.T) {
	fake := &fakeGitClient{err: fmt.Errorf("revert conflict")}
	state := preloadedState(t.TempDir(), "remediation/run-001")
	state.SetBaseBranch("main")
	handler := git.HandleRevertCommit(fake, state, git.ProtectedBranches{}, time.Millisecond, testMaxWaitSeconds)

	result, err := callHandler(t, "revert_commit", revertCommitTool(), handler, map[string]any{
		"merge_commit_sha": "deadbeef",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for domain error")
	}
	if text := result.Content[0].(mcp.TextContent).Text; !strings.Contains(text, "revert conflict") {
		t.Errorf("expected revert error in response, got: %s", text)
	}
}

func TestRevertCommitHandler_InvalidSHA(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{}
	state := preloadedState(cloneDir, "remediation/run-001")
	tool := revertCommitTool()
	handler := git.HandleRevertCommit(fake, state, git.ProtectedBranches{}, time.Millisecond, testMaxWaitSeconds)

	result, err := callHandler(t, "revert_commit", tool, handler, map[string]any{
		"merge_commit_sha": "not-a-sha!",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for invalid SHA format")
	}
}

func TestClosePRHandler_Success(t *testing.T) {
	fake := &fakeGitClient{}
	state := &fakeSessionState{}
	tool := mcp.NewTool("close_pr", mcp.WithNumber("pr_number", mcp.Required()))
	handler := git.HandleClosePR(fake, state)

	result, err := callHandler(t, "close_pr", tool, handler, map[string]any{"pr_number": float64(42)})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success, got error: %v", result.Content)
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "pr #42 closed") {
		t.Errorf("expected confirmation in response, got: %s", text)
	}
}

func TestClosePRHandler_DomainError(t *testing.T) {
	fake := &fakeGitClient{closePRErr: fmt.Errorf("gh: failed")}
	state := &fakeSessionState{}
	tool := mcp.NewTool("close_pr", mcp.WithNumber("pr_number", mcp.Required()))
	handler := git.HandleClosePR(fake, state)

	result, err := callHandler(t, "close_pr", tool, handler, map[string]any{"pr_number": float64(42)})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for domain error")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "HandleClosePR:") {
		t.Errorf("expected 'HandleClosePR:' in error message, got: %s", text)
	}
	if !strings.Contains(text, "gh: failed") {
		t.Errorf("expected underlying error in message, got: %s", text)
	}
}

func TestClosePRHandler_MissingArgument(t *testing.T) {
	fake := &fakeGitClient{}
	state := &fakeSessionState{}
	tool := mcp.NewTool("close_pr", mcp.WithNumber("pr_number", mcp.Required()))
	handler := git.HandleClosePR(fake, state)

	result, err := callHandler(t, "close_pr", tool, handler, map[string]any{})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for missing pr_number")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "pr_number") {
		t.Errorf("expected 'pr_number' in error message, got: %s", text)
	}
}

func TestDeleteBranchHandler_Success(t *testing.T) {
	fake := &fakeGitClient{}
	state := &fakeSessionState{}
	tool := mcp.NewTool("delete_branch", mcp.WithString("branch", mcp.Required()))
	handler := git.HandleDeleteBranch(fake, state, git.ProtectedBranches{}, testMaxBytes)

	result, err := callHandler(t, "delete_branch", tool, handler, map[string]any{"branch": "remediation/run-k8s-1"})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success, got error: %v", result.Content)
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "branch deleted: remediation/run-k8s-1") {
		t.Errorf("expected confirmation in response, got: %s", text)
	}
}

func TestDeleteBranchHandler_DomainError(t *testing.T) {
	fake := &fakeGitClient{deleteBranchErr: fmt.Errorf("gh: not found")}
	state := &fakeSessionState{}
	tool := mcp.NewTool("delete_branch", mcp.WithString("branch", mcp.Required()))
	handler := git.HandleDeleteBranch(fake, state, git.ProtectedBranches{}, testMaxBytes)

	result, err := callHandler(t, "delete_branch", tool, handler, map[string]any{"branch": "remediation/run-k8s-1"})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for domain error")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "HandleDeleteBranch:") {
		t.Errorf("expected 'HandleDeleteBranch:' in error message, got: %s", text)
	}
}

func TestDeleteBranchHandler_MissingArgument(t *testing.T) {
	fake := &fakeGitClient{}
	state := &fakeSessionState{}
	tool := mcp.NewTool("delete_branch", mcp.WithString("branch", mcp.Required()))
	handler := git.HandleDeleteBranch(fake, state, git.ProtectedBranches{}, testMaxBytes)

	result, err := callHandler(t, "delete_branch", tool, handler, map[string]any{})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for missing branch")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "branch") {
		t.Errorf("expected 'branch' in error message, got: %s", text)
	}
}

func TestPushBranchHandler_RefusesProtected(t *testing.T) {
	fake := &fakeGitClient{}
	state := preloadedState(t.TempDir(), "main")
	tool := mcp.NewTool("push_branch")
	handler := git.HandlePushBranch(fake, state, git.ProtectedBranches{"main": {}}, testMaxBytes)

	result, err := callHandler(t, "push_branch", tool, handler, map[string]any{})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for protected branch")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "branch is protected") {
		t.Errorf("expected 'branch is protected' in error, got: %s", text)
	}
	if fake.pushCalls != 0 {
		t.Errorf("expected Push not called, got %d", fake.pushCalls)
	}
}

func TestRevertCommitHandler_RefusesProtectedBase(t *testing.T) {
	cloneDir := t.TempDir()
	fake := mergedRevertClient()
	state := preloadedState(cloneDir, "remediation/run-001")
	state.SetBaseBranch("main")
	tool := revertCommitTool()
	handler := git.HandleRevertCommit(fake, state, git.ProtectedBranches{"main": {}}, time.Millisecond, testMaxWaitSeconds)

	result, err := callHandler(t, "revert_commit", tool, handler, map[string]any{
		"merge_commit_sha": "abc1234",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for protected base branch")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "branch is protected") {
		t.Errorf("expected 'branch is protected' in error, got: %s", text)
	}
	if fake.lastRevertBranch != "" {
		t.Errorf("expected RevertCommit not called, got branch %q", fake.lastRevertBranch)
	}
}

func TestRevertCommitHandler_AllowsEvalBaseline(t *testing.T) {
	cloneDir := t.TempDir()
	fake := mergedRevertClient()
	state := preloadedState(cloneDir, "remediation/run-001")
	state.SetBaseBranch("chore/eval-cluster-baseline")
	tool := revertCommitTool()
	handler := git.HandleRevertCommit(fake, state, git.ProtectedBranches{"main": {}}, time.Millisecond, testMaxWaitSeconds)

	result, err := callHandler(t, "revert_commit", tool, handler, map[string]any{
		"merge_commit_sha": "abc1234",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success, got error: %v", result.Content)
	}
	if fake.lastRevertBranch != "chore/eval-cluster-baseline" {
		t.Errorf("expected lastRevertBranch %q, got %q", "chore/eval-cluster-baseline", fake.lastRevertBranch)
	}
}

func TestDeleteBranchHandler_RefusesProtected(t *testing.T) {
	fake := &fakeGitClient{}
	state := &fakeSessionState{}
	tool := mcp.NewTool("delete_branch", mcp.WithString("branch", mcp.Required()))
	handler := git.HandleDeleteBranch(fake, state, git.ProtectedBranches{"main": {}}, testMaxBytes)

	result, err := callHandler(t, "delete_branch", tool, handler, map[string]any{"branch": "main"})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for protected branch")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "branch is protected") {
		t.Errorf("expected 'branch is protected' in error, got: %s", text)
	}
	if fake.deleteBranchCalls != 0 {
		t.Errorf("expected DeleteBranch not called, got %d", fake.deleteBranchCalls)
	}
}

func TestReadFileHandler_Success(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{readFileOut: "apiVersion: v1\nkind: ConfigMap\n"}
	state := preloadedState(cloneDir, "chore/eval-cluster-baseline")
	tool := mcp.NewTool("read_file",
		mcp.WithString("branch", mcp.Required()),
		mcp.WithString("path", mcp.Required()),
	)
	handler := git.HandleReadFile(fake, state, "", testMaxBytes)

	result, err := callHandler(t, "read_file", tool, handler, map[string]any{
		"branch": "chore/eval-cluster-baseline",
		"path":   "infra/k8s/cm.yaml",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success, got error: %v", result.Content)
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "apiVersion: v1") {
		t.Errorf("expected YAML in response, got: %s", text)
	}
}

func TestReadFileHandler_BranchNotFound(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{readFileErr: errors.New("branch not found: missing-branch")}
	state := preloadedState(cloneDir, "chore/eval-cluster-baseline")
	tool := mcp.NewTool("read_file",
		mcp.WithString("branch", mcp.Required()),
		mcp.WithString("path", mcp.Required()),
	)
	handler := git.HandleReadFile(fake, state, "", testMaxBytes)

	result, err := callHandler(t, "read_file", tool, handler, map[string]any{
		"branch": "missing-branch",
		"path":   "infra/k8s/cm.yaml",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for branch not found")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "branch not found") {
		t.Errorf("expected 'branch not found' in error, got: %s", text)
	}
}

func TestReadFileHandler_PathNotFound(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{readFileErr: errors.New("path not found: nope.yaml")}
	state := preloadedState(cloneDir, "chore/eval-cluster-baseline")
	tool := mcp.NewTool("read_file",
		mcp.WithString("branch", mcp.Required()),
		mcp.WithString("path", mcp.Required()),
	)
	handler := git.HandleReadFile(fake, state, "", testMaxBytes)

	result, err := callHandler(t, "read_file", tool, handler, map[string]any{
		"branch": "chore/eval-cluster-baseline",
		"path":   "nope.yaml",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for path not found")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "path not found") {
		t.Errorf("expected 'path not found' in error, got: %s", text)
	}
}

func TestReadFileHandler_MissingBranch(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{}
	state := preloadedState(cloneDir, "chore/eval-cluster-baseline")
	tool := mcp.NewTool("read_file",
		mcp.WithString("branch", mcp.Required()),
		mcp.WithString("path", mcp.Required()),
	)
	handler := git.HandleReadFile(fake, state, "", testMaxBytes)

	result, err := callHandler(t, "read_file", tool, handler, map[string]any{
		"path": "infra/k8s/cm.yaml",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for missing branch")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "branch") {
		t.Errorf("expected 'branch' in error, got: %s", text)
	}
}

func TestReadFileHandler_MissingPath(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{}
	state := preloadedState(cloneDir, "chore/eval-cluster-baseline")
	tool := mcp.NewTool("read_file",
		mcp.WithString("branch", mcp.Required()),
		mcp.WithString("path", mcp.Required()),
	)
	handler := git.HandleReadFile(fake, state, "", testMaxBytes)

	result, err := callHandler(t, "read_file", tool, handler, map[string]any{
		"branch": "chore/eval-cluster-baseline",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for missing path")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "path") {
		t.Errorf("expected 'path' in error, got: %s", text)
	}
}

func TestReadFileHandler_SessionNotInitialised(t *testing.T) {
	fake := &fakeGitClient{}
	state := &fakeSessionState{}
	tool := mcp.NewTool("read_file",
		mcp.WithString("branch", mcp.Required()),
		mcp.WithString("path", mcp.Required()),
	)
	handler := git.HandleReadFile(fake, state, "", testMaxBytes)

	result, err := callHandler(t, "read_file", tool, handler, map[string]any{
		"branch": "chore/eval-cluster-baseline",
		"path":   "infra/k8s/cm.yaml",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true when session not initialised and no repo URL")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "clone_repo") {
		t.Errorf("expected 'clone_repo' in error, got: %s", text)
	}
}

func TestReadFileHandler_AutoClone_Success(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{cloneDir: cloneDir, readFileOut: "apiVersion: v1\nkind: Deployment\n"}
	state := &fakeSessionState{}
	tool := mcp.NewTool("read_file",
		mcp.WithString("branch", mcp.Required()),
		mcp.WithString("path", mcp.Required()),
	)
	handler := git.HandleReadFile(fake, state, "https://token@github.com/org/repo", testMaxBytes)

	result, err := callHandler(t, "read_file", tool, handler, map[string]any{
		"branch": "main",
		"path":   "infra/k8s/deploy.yaml",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success with auto-clone, got error: %v", result.Content)
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "apiVersion: v1") {
		t.Errorf("expected file content in response, got: %s", text)
	}
	if state.CloneDir() != cloneDir {
		t.Errorf("expected session to be initialised after auto-clone, cloneDir=%s", state.CloneDir())
	}
}

func TestReadFileHandler_AutoClone_CloneFails(t *testing.T) {
	fake := &fakeGitClient{err: errors.New("authentication failed")}
	state := &fakeSessionState{}
	tool := mcp.NewTool("read_file",
		mcp.WithString("branch", mcp.Required()),
		mcp.WithString("path", mcp.Required()),
	)
	handler := git.HandleReadFile(fake, state, "https://bad-token@github.com/org/repo", testMaxBytes)

	result, err := callHandler(t, "read_file", tool, handler, map[string]any{
		"branch": "main",
		"path":   "infra/k8s/deploy.yaml",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true when auto-clone fails")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "auto-clone") {
		t.Errorf("expected 'auto-clone' in error, got: %s", text)
	}
}

func nixInstantiateAvailable(t *testing.T) {
	t.Helper()
	if _, err := exec.LookPath("nix-instantiate"); err != nil {
		t.Skip("nix-instantiate not in PATH")
	}
}

func TestHandleWriteManifest_NixSyntaxValid(t *testing.T) {
	nixInstantiateAvailable(t)
	cloneDir := t.TempDir()
	seedManifest(t, cloneDir, "hosts/worker-1.nix", "{ pkgs, ... }: {}\n")
	fake := &fakeGitClient{}
	state := preloadedState(cloneDir, "remediation/run-001")
	tool := mcp.NewTool("write_manifest",
		mcp.WithString("manifest_path", mcp.Required()),
		mcp.WithString("patch_body", mcp.Required()),
	)
	handler := git.HandleWriteManifest(fake, state, testMaxBytes)

	result, err := callHandler(t, "write_manifest", tool, handler, map[string]any{
		"manifest_path": "hosts/worker-1.nix",
		"patch_body":    "{ pkgs, ... }: { services.foo.enable = true; }\n",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success for valid Nix content, got error: %v", result.Content)
	}
}

func TestHandleWriteManifest_NixSyntaxInvalid(t *testing.T) {
	nixInstantiateAvailable(t)
	cloneDir := t.TempDir()
	seedManifest(t, cloneDir, "hosts/worker-1.nix", "{ pkgs, ... }: {}\n")
	fake := &fakeGitClient{}
	state := preloadedState(cloneDir, "remediation/run-001")
	tool := mcp.NewTool("write_manifest",
		mcp.WithString("manifest_path", mcp.Required()),
		mcp.WithString("patch_body", mcp.Required()),
	)
	handler := git.HandleWriteManifest(fake, state, testMaxBytes)

	result, err := callHandler(t, "write_manifest", tool, handler, map[string]any{
		"manifest_path": "hosts/worker-1.nix",
		"patch_body":    "{ services.foo.enable = true;\n",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for malformed Nix content")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "nix syntax error") {
		t.Errorf("expected 'nix syntax error' in error message, got: %s", text)
	}
}

func TestHandleWriteManifest_YamlRuntimeFieldStillCaught(t *testing.T) {
	cloneDir := t.TempDir()
	seedManifest(t, cloneDir, "apps/deploy.yaml", "apiVersion: v1\nkind: Deployment\nmetadata:\n  name: foo\n")
	fake := &fakeGitClient{}
	state := preloadedState(cloneDir, "remediation/run-001")
	tool := mcp.NewTool("write_manifest",
		mcp.WithString("manifest_path", mcp.Required()),
		mcp.WithString("patch_body", mcp.Required()),
	)
	handler := git.HandleWriteManifest(fake, state, testMaxBytes)

	result, err := callHandler(t, "write_manifest", tool, handler, map[string]any{
		"manifest_path": "apps/deploy.yaml",
		"patch_body":    "apiVersion: v1\nkind: Deployment\nmetadata:\n  name: foo\n  creationTimestamp: \"2026-01-01T00:00:00Z\"\n",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for YAML with runtime-only field")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "creationTimestamp") {
		t.Errorf("expected 'creationTimestamp' in error message, got: %s", text)
	}
}

func TestHandleWriteManifest_YamlValidPasses(t *testing.T) {
	cloneDir := t.TempDir()
	seedManifest(t, cloneDir, "apps/deploy.yaml", "apiVersion: v1\nkind: Deployment\nmetadata:\n  name: foo\n")
	fake := &fakeGitClient{}
	state := preloadedState(cloneDir, "remediation/run-001")
	tool := mcp.NewTool("write_manifest",
		mcp.WithString("manifest_path", mcp.Required()),
		mcp.WithString("patch_body", mcp.Required()),
	)
	handler := git.HandleWriteManifest(fake, state, testMaxBytes)

	result, err := callHandler(t, "write_manifest", tool, handler, map[string]any{
		"manifest_path": "apps/deploy.yaml",
		"patch_body":    "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: foo\nspec:\n  replicas: 2\n",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success for valid YAML content, got error: %v", result.Content)
	}
}

func TestSessionStateMutex_Concurrent(t *testing.T) {
	s := &gitserver.GitServer{}
	var wg sync.WaitGroup
	wg.Add(concurrentGoroutines)
	for i := range concurrentGoroutines {
		go func(n int) {
			defer wg.Done()
			runID := fmt.Sprintf("run-%d", n)
			s.BeginSession(runID, t.TempDir())
			s.SetBranch("remediation/run-" + runID)
			_, _ = s.Branch()
		}(i)
	}
	wg.Wait()
}

func TestGitServer_BaseBranchDefaultEmpty(t *testing.T) {
	s := &gitserver.GitServer{}
	if got := s.BaseBranch(); got != "" {
		t.Errorf("expected empty string before SetBaseBranch, got %q", got)
	}
}

func TestGitServer_SetBaseBranchPersists(t *testing.T) {
	s := &gitserver.GitServer{}
	s.SetBaseBranch("eval-baseline")
	if got := s.BaseBranch(); got != "eval-baseline" {
		t.Errorf("expected %q, got %q", "eval-baseline", got)
	}
}

func TestGitServer_BaseBranchConcurrent(t *testing.T) {
	s := &gitserver.GitServer{}
	var wg sync.WaitGroup
	wg.Add(concurrentGoroutines)
	for i := range concurrentGoroutines {
		go func(n int) {
			defer wg.Done()
			s.SetBaseBranch(fmt.Sprintf("branch-%d", n))
			_ = s.BaseBranch()
		}(i)
	}
	wg.Wait()
}

func TestHandleCreateBranch_PreservesBaseBranchFromCloneRepo(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{}
	state := preloadedState(cloneDir, "")
	state.SetBaseBranch("chore/eval-cluster-baseline")
	tool := mcp.NewTool("create_branch",
		mcp.WithString("run_id", mcp.Required()),
		mcp.WithString("base_branch"),
	)
	handler := git.HandleCreateBranch(fake, state, testMaxBytes)

	result, err := callHandler(t, "create_branch", tool, handler, map[string]any{"run_id": "abc123"})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success, got error: %v", result.Content)
	}
	if got := state.BaseBranch(); got != "chore/eval-cluster-baseline" {
		t.Errorf("expected baseBranch preserved as %q, got %q", "chore/eval-cluster-baseline", got)
	}
}

func TestHandleCreateBranch_BaseBranchExplicitOverride(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{}
	state := preloadedState(cloneDir, "")
	state.SetBaseBranch("main")
	tool := mcp.NewTool("create_branch",
		mcp.WithString("run_id", mcp.Required()),
		mcp.WithString("base_branch"),
	)
	handler := git.HandleCreateBranch(fake, state, testMaxBytes)

	result, err := callHandler(t, "create_branch", tool, handler, map[string]any{
		"run_id":      "abc456",
		"base_branch": "eval-baseline",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success, got error: %v", result.Content)
	}
	if got := state.BaseBranch(); got != "eval-baseline" {
		t.Errorf("expected baseBranch %q, got %q", "eval-baseline", got)
	}
}

func TestHandleRevertCommit_UsesBaseBranchFromSession(t *testing.T) {
	cloneDir := t.TempDir()
	fake := mergedRevertClient()
	state := preloadedState(cloneDir, "remediation/run-001")
	state.SetBaseBranch("chore/eval-cluster-baseline")

	tool := revertCommitTool()
	handler := git.HandleRevertCommit(fake, state, git.ProtectedBranches{}, time.Millisecond, testMaxWaitSeconds)

	result, err := callHandler(t, "revert_commit", tool, handler, map[string]any{
		"merge_commit_sha": "deadbeef",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success, got error: %v", result.Content)
	}
	if got := fake.lastRevertBranch; got != "chore/eval-cluster-baseline" {
		t.Errorf("expected lastRevertBranch %q, got %q", "chore/eval-cluster-baseline", got)
	}
	if fake.gotBase != "chore/eval-cluster-baseline" {
		t.Errorf("expected revert PR base %q, got %q", "chore/eval-cluster-baseline", fake.gotBase)
	}
	branch, _ := state.Branch()
	if branch != "remediation/revert-deadbeef" {
		t.Errorf("expected session branch %q after revert, got %q", "remediation/revert-deadbeef", branch)
	}
}

func TestHandleRevertCommit_FailsWhenBaseBranchUnset(t *testing.T) {
	cloneDir := t.TempDir()
	fake := mergedRevertClient()
	state := preloadedState(cloneDir, "remediation/run-001")

	tool := revertCommitTool()
	handler := git.HandleRevertCommit(fake, state, git.ProtectedBranches{}, time.Millisecond, testMaxWaitSeconds)

	result, err := callHandler(t, "revert_commit", tool, handler, map[string]any{
		"merge_commit_sha": "deadbeef",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true when base branch is unset in session")
	}
}

func TestRealGitClient_RevertCommitFetchError(t *testing.T) {
	repoDir := t.TempDir()
	if out, err := exec.Command("git", "-C", repoDir, "init").CombinedOutput(); err != nil {
		t.Fatalf("git init: %v: %s", err, out)
	}
	if out, err := exec.Command("git", "-C", repoDir, "config", "user.email", "test@example.com").CombinedOutput(); err != nil {
		t.Fatalf("git config user.email: %v: %s", err, out)
	}
	if out, err := exec.Command("git", "-C", repoDir, "config", "user.name", "Test").CombinedOutput(); err != nil {
		t.Fatalf("git config user.name: %v: %s", err, out)
	}
	if out, err := exec.Command("git", "-C", repoDir, "commit", "--allow-empty", "-m", "init").CombinedOutput(); err != nil {
		t.Fatalf("git commit: %v: %s", err, out)
	}

	cfg := &config.Config{
		GitHubToken: "tok",
		RepoURL:     "https://github.com/x/y.git",
	}
	client := git.NewRealGitClient(cfg, auth.Identity{Token: auth.Static(cfg.GitHubToken)})

	_, err := client.RevertCommit(context.Background(), repoDir, "deadbeef", "chore/eval-cluster-baseline", "remediation/revert-deadbeef")
	if err == nil {
		t.Fatal("expected error for missing origin remote, got nil")
	}
	if !strings.HasPrefix(err.Error(), "revert_commit: fetch:") {
		t.Errorf("expected 'revert_commit: fetch:' prefix, got: %v", err)
	}
}

func TestWaitForGate_reportsLastErrorAtDeadline(t *testing.T) {
	const lastError = "get_pr_status: 502 Bad Gateway"
	fake := &fakeGitClient{err: errors.New(lastError)}

	result := runWaitForGate(t, fake, shortWaitSeconds)

	if !result.IsError {
		t.Fatal("expected IsError=true when every poll errors")
	}
	text := resultText(result)
	if !strings.Contains(text, lastError) || !strings.Contains(text, "gate wait ended after 1 seconds") {
		t.Errorf("expected last error and deadline end in result, got: %s", text)
	}
	if fake.getPRCalls <= minPollsBeforeDeadline {
		t.Errorf("expected polling to continue past errors, got %d status reads", fake.getPRCalls)
	}
}

func TestWaitForGate_reportsCheckRunErrorAtDeadline(t *testing.T) {
	const checkRunError = "get_check_run_status: list runs: 403 Resource not accessible by integration"
	fake := &fakeGitClient{prState: "open", checkRunErr: errors.New(checkRunError)}

	result := runWaitForGate(t, fake, shortWaitSeconds)

	if text := resultText(result); !result.IsError || !strings.Contains(text, "gate wait ended after 1 seconds ("+checkRunError+")") {
		t.Errorf("expected the check run error named at the deadline, got: %s", text)
	}
}

const minPollsBeforeDeadline = 2

const (
	transientFailures    = 1
	openPollsBeforeMerge = 3
)

type flakyStatusClient struct {
	*fakeGitClient
	calls int
}

func (f *flakyStatusClient) GetPRStatus(_ context.Context, _ int) (string, bool, string, error) {
	f.calls++
	switch {
	case f.calls <= transientFailures:
		return "", false, "", errors.New("get_pr_status: GET .../pulls/42: 502 Bad Gateway")
	case f.calls <= transientFailures+openPollsBeforeMerge:
		return "open", false, "", nil
	}
	return "closed", true, "deadbeef", nil
}

func TestWaitForGate_survivesTransientStatusError(t *testing.T) {
	client := &flakyStatusClient{fakeGitClient: &fakeGitClient{}}
	handler := git.HandleWaitForGate(client, sessionWithPR(42), time.Millisecond, testMaxWaitSeconds)
	result, err := callHandler(t, "wait_for_gate", waitForGateTool(), handler, map[string]any{"pr_number": float64(42)})
	if err != nil {
		t.Fatal(err)
	}
	if result.IsError {
		t.Fatalf("a transient status error ended the wait: %s", resultText(result))
	}
	if structured, ok := result.StructuredContent.(map[string]any); !ok || structured["merge_commit_sha"] != "deadbeef" {
		t.Errorf("structured result = %#v, want merge_commit_sha deadbeef", result.StructuredContent)
	}
}

const (
	gatedHead      = "abc123"
	apiMergeSHA    = "feedface"
	terminalWithin = 500 * time.Millisecond
)

func passingGateClient() *fakeGitClient {
	return &fakeGitClient{prState: "open", checkRunConclusion: "success", checkRunHeadSHA: gatedHead, mergeSHA: apiMergeSHA}
}

func TestWaitForGate_mergesWhenGatePasses(t *testing.T) {
	fake := passingGateClient()

	result := runWaitForGate(t, fake, testMaxWaitSeconds)

	if result.IsError {
		t.Fatalf("expected the PR merged once the gate passed, got: %s", resultText(result))
	}
	if fake.mergeCalls != 1 || fake.mergeHeadSHA != gatedHead {
		t.Errorf("MergePR calls = %d with head %q, want 1 with %s", fake.mergeCalls, fake.mergeHeadSHA, gatedHead)
	}
	if structured, ok := result.StructuredContent.(map[string]any); !ok || structured["merge_commit_sha"] != apiMergeSHA {
		t.Errorf("structured result = %#v, want merge_commit_sha %s", result.StructuredContent, apiMergeSHA)
	}
}

func TestWaitForGate_headMovedEndsWait(t *testing.T) {
	fake := passingGateClient()
	fake.mergeErr = fmt.Errorf("merge_pr #42: %w", git.ErrHeadMoved)

	start := time.Now()
	result := runWaitForGate(t, fake, testMaxWaitSeconds)

	if elapsed := time.Since(start); elapsed > terminalWithin {
		t.Errorf("wait took %v after the head moved, want it to end at once", elapsed)
	}
	text := resultText(result)
	if !result.IsError || fake.mergeCalls != 1 || !strings.Contains(text, git.ErrHeadMoved.Error()) || !strings.Contains(text, "PR #42 open and not merged") {
		t.Errorf("expected one merge attempt ending the wait as a failure, got %d attempts: %s", fake.mergeCalls, text)
	}
}

func TestWaitForGate_skippedGateDoesNotMerge(t *testing.T) {
	fake := passingGateClient()
	fake.checkRunConclusion = "skipped"

	result := runWaitForGate(t, fake, shortWaitSeconds)

	text := resultText(result)
	if !result.IsError || fake.mergeCalls != 0 {
		t.Errorf("expected no merge for a skipped gate, got %d merge calls: %s", fake.mergeCalls, text)
	}
	if !strings.Contains(text, "gate wait ended after 1 seconds") || !strings.Contains(text, "skipped") {
		t.Errorf("expected the deadline end naming the conclusion, got: %s", text)
	}
}

func TestWaitForGate_externalMergeWins(t *testing.T) {
	fake := passingGateClient()
	fake.prState, fake.prMerged, fake.prMergeSHA = "closed", true, "1a7e5ha"

	result := runWaitForGate(t, fake, testMaxWaitSeconds)

	if result.IsError || fake.mergeCalls != 0 {
		t.Fatalf("expected the existing merge returned without a merge call, got %d calls: %s", fake.mergeCalls, resultText(result))
	}
	if structured, ok := result.StructuredContent.(map[string]any); !ok || structured["merge_commit_sha"] != "1a7e5ha" {
		t.Errorf("structured result = %#v, want merge_commit_sha 1a7e5ha", result.StructuredContent)
	}
}

func TestWaitForGate_notMergeableUntilDeadline(t *testing.T) {
	fake := passingGateClient()
	fake.mergeErr = errors.New("merge_pr #42: PUT .../pulls/42/merge: 405 Pull Request is not mergeable")

	result := runWaitForGate(t, fake, shortWaitSeconds)

	text := resultText(result)
	if !result.IsError || !strings.Contains(text, "gate wait ended after 1 seconds") || !strings.Contains(text, "PR #42 open and not merged") {
		t.Errorf("expected the deadline end with the PR open and not merged, got: %s", text)
	}
	if fake.mergeCalls < minPollsBeforeDeadline {
		t.Errorf("expected a merge attempt on every passing poll, got %d", fake.mergeCalls)
	}
}

func TestWaitForGate_mergeCallOutlivesDeadline(t *testing.T) {
	fake := passingGateClient()
	fake.mergeDelay = shortWaitSeconds*time.Second + terminalWithin

	result := runWaitForGate(t, fake, shortWaitSeconds)

	if result.IsError {
		t.Fatalf("the deadline cut short an in-flight merge: %s", resultText(result))
	}
	if !fake.mergeHasDeadline {
		t.Error("expected the merge call to run under its own timeout")
	}
	if structured, ok := result.StructuredContent.(map[string]any); !ok || structured["merge_commit_sha"] != apiMergeSHA {
		t.Errorf("structured result = %#v, want merge_commit_sha %s", result.StructuredContent, apiMergeSHA)
	}
}

func TestWaitForGate_reportsLastMergeError(t *testing.T) {
	const forbidden = "merge_pr #42: PUT .../pulls/42/merge: 403 Resource not accessible by integration"

	t.Run("every poll", func(t *testing.T) {
		fake := passingGateClient()
		fake.mergeErr = errors.New(forbidden)

		result := runWaitForGate(t, fake, shortWaitSeconds)

		if text := resultText(result); !result.IsError || !strings.Contains(text, "gate wait ended after 1 seconds ("+forbidden+")") {
			t.Errorf("expected the merge error named at the deadline, got: %s", text)
		}
	})

	t.Run("cleared by a clean poll", func(t *testing.T) {
		fake := passingGateClient()
		fake.mergeErr = errors.New(forbidden)
		fake.onMerge = func(f *fakeGitClient) { f.checkRunConclusion = "" }

		result := runWaitForGate(t, fake, shortWaitSeconds)

		if text := resultText(result); !result.IsError || strings.Contains(text, forbidden) || !strings.Contains(text, "gate wait ended after 1 seconds; PR #42 open and not merged") {
			t.Errorf("expected a cleared merge error to stay unreported, got: %s", text)
		}
	})
}

func createPRInSession(t *testing.T, fake *fakeGitClient, state *fakeSessionState) {
	t.Helper()
	state.SetBaseBranch("main")
	state.SetBranch("remediation/run-001")
	tool := mcp.NewTool("create_pr", mcp.WithString("title", mcp.Required()), mcp.WithString("body", mcp.Required()))
	result, err := callHandler(t, "create_pr", tool, git.HandleCreatePR(fake, state), map[string]any{"title": "fix: raise memory limit", "body": "Automated remediation"})
	if err != nil || result.IsError {
		t.Fatalf("create_pr: %v %v", err, result)
	}
}

func TestWaitForGate_mergesOnlyThePRCreatedInSession(t *testing.T) {
	const foreignPR = 7

	t.Run("pr created in session", func(t *testing.T) {
		fake := passingGateClient()
		fake.prNumber = 42
		state := &fakeSessionState{}
		createPRInSession(t, fake, state)

		result, err := callHandler(t, "wait_for_gate", waitForGateTool(), git.HandleWaitForGate(fake, state, time.Millisecond, testMaxWaitSeconds), map[string]any{"pr_number": float64(42)})

		if err != nil || result.IsError || fake.mergeCalls != 1 {
			t.Errorf("expected the session PR merged once, got %d merge calls: %v %v", fake.mergeCalls, err, result)
		}
	})

	t.Run("foreign pr", func(t *testing.T) {
		fake := passingGateClient()
		fake.prNumber = 42
		state := &fakeSessionState{}
		createPRInSession(t, fake, state)

		result, err := callHandler(t, "wait_for_gate", waitForGateTool(), git.HandleWaitForGate(fake, state, time.Millisecond, testMaxWaitSeconds), map[string]any{"pr_number": float64(foreignPR)})

		if err != nil || !result.IsError || fake.mergeCalls != 0 || fake.getPRCalls != 0 {
			t.Errorf("expected a refusal without reads or merges, got %d merge calls, %d reads: %v %v", fake.mergeCalls, fake.getPRCalls, err, result)
		}
	})

	t.Run("no pr created", func(t *testing.T) {
		fake := passingGateClient()

		result, err := callHandler(t, "wait_for_gate", waitForGateTool(), git.HandleWaitForGate(fake, &fakeSessionState{}, time.Millisecond, testMaxWaitSeconds), map[string]any{"pr_number": float64(42)})

		if err != nil || !result.IsError || fake.mergeCalls != 0 || fake.getPRCalls != 0 {
			t.Errorf("expected a refusal without reads or merges, got %d merge calls, %d reads: %v %v", fake.mergeCalls, fake.getPRCalls, err, result)
		}
	})
}

func TestWaitForGate_readsMergeSHAFromPRWhenMergeResponseLacksIt(t *testing.T) {
	fake := passingGateClient()
	fake.mergeSHA = ""
	fake.onMerge = func(f *fakeGitClient) { f.prState, f.prMerged, f.prMergeSHA = "closed", true, apiMergeSHA }

	result := runWaitForGate(t, fake, testMaxWaitSeconds)

	if result.IsError || fake.mergeCalls != 1 {
		t.Fatalf("expected one merge and success, got %d merge calls: %s", fake.mergeCalls, resultText(result))
	}
	if structured, ok := result.StructuredContent.(map[string]any); !ok || structured["merge_commit_sha"] != apiMergeSHA {
		t.Errorf("structured result = %#v, want merge_commit_sha %s", result.StructuredContent, apiMergeSHA)
	}
}
