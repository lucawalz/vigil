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

	"github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/config"
	"github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/git"
	gitserver "github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/server"
)

const (
	testMaxBytes         = 4096
	concurrentGoroutines = 100
)

type fakeGitClient struct {
	cloneDir              string
	gotBaseBranch         string
	gotBase               string
	commitSHA             string
	prNumber              int
	prState               string
	prMerged              bool
	prMergeSHA            string
	revertSHA             string
	lastRevertBranch      string
	err                   error
	getPRCalls            int
	autoMergeErr          error
	autoMergeCalls        int
	closePRErr            error
	closePRCalls          int
	deleteBranchErr       error
	deleteBranchCalls     int
	readFileOut           string
	readFileErr           error
	checkRunFailed        bool
	checkRunConclusion    string
	checkRunErr           error
}

var _ git.GitClient = &fakeGitClient{}

func (f *fakeGitClient) Clone(_ context.Context, _, baseBranch string) (string, error) {
	f.gotBaseBranch = baseBranch
	return f.cloneDir, f.err
}

func (f *fakeGitClient) CreateBranch(_ context.Context, _, _ string) error {
	return f.err
}

func (f *fakeGitClient) WriteFile(_ context.Context, _, _, _ string) error {
	return f.err
}

func (f *fakeGitClient) CommitFiles(_ context.Context, _, _, _ string) (string, error) {
	return f.commitSHA, f.err
}

func (f *fakeGitClient) Push(_ context.Context, _, _ string) error {
	return f.err
}

func (f *fakeGitClient) CreatePR(_ context.Context, _, _, base, _ string) (int, error) {
	f.gotBase = base
	return f.prNumber, f.err
}

func (f *fakeGitClient) EnableAutoMerge(_ context.Context, _ int) error {
	f.autoMergeCalls++
	return f.autoMergeErr
}

func (f *fakeGitClient) GetPRStatus(_ context.Context, _ int) (string, bool, string, error) {
	f.getPRCalls++
	return f.prState, f.prMerged, f.prMergeSHA, f.err
}

func (f *fakeGitClient) RevertCommit(_ context.Context, _, _, branch string) (string, error) {
	f.lastRevertBranch = branch
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

func (f *fakeGitClient) GetCheckRunStatus(_ context.Context, _ int) (bool, string, error) {
	return f.checkRunFailed, f.checkRunConclusion, f.checkRunErr
}

type fakeSessionState struct {
	mu            sync.Mutex
	runID         string
	cloneDir      string
	currentBranch string
	baseBranch    string
	lastCommitSHA string
}

var _ git.SessionState = &fakeSessionState{}

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
	handler := git.HandleCloneRepo(fake, state, cfg.AuthURL(), testMaxBytes)

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

func TestCommitFilesHandler_Success(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{commitSHA: "abc1234"}
	state := preloadedState(cloneDir, "remediation/run-001")
	tool := mcp.NewTool("commit_files", mcp.WithString("message", mcp.Required()))
	handler := git.HandleCommitFiles(fake, state, testMaxBytes)

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
	handler := git.HandleCommitFiles(fake, state, testMaxBytes)

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
	handler := git.HandleCommitFiles(fake, state, testMaxBytes)

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
	handler := git.HandlePushBranch(fake, state, testMaxBytes)

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
	handler := git.HandlePushBranch(fake, state, testMaxBytes)

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
	handler := git.HandlePushBranch(fake, state, testMaxBytes)

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
	handler := git.HandleCreatePR(fake, state, testMaxBytes)

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
	if fake.autoMergeCalls != 1 {
		t.Errorf("expected EnableAutoMerge called once, got %d", fake.autoMergeCalls)
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
	handler := git.HandleCreatePR(fake, state, testMaxBytes)

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
	handler := git.HandleCreatePR(fake, state, testMaxBytes)

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
	handler := git.HandleCreatePR(fake, state, testMaxBytes)

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

func TestCreatePRHandler_AutoMergeError(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{prNumber: 42, autoMergeErr: fmt.Errorf("gh: authentication required")}
	state := preloadedState(cloneDir, "remediation/run-001")
	state.SetBaseBranch("main")
	tool := mcp.NewTool("create_pr",
		mcp.WithString("title", mcp.Required()),
		mcp.WithString("body", mcp.Required()),
	)
	handler := git.HandleCreatePR(fake, state, testMaxBytes)

	result, err := callHandler(t, "create_pr", tool, handler, map[string]any{
		"title": "fix: reduce OOMKilled replicas",
		"body":  "Automated remediation",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true when EnableAutoMerge fails")
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
	handler := git.HandleCreatePR(fake, state, testMaxBytes)

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
	handler := git.HandleGetPRStatus(fake, state, testMaxBytes)

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
	handler := git.HandleGetPRStatus(fake, state, testMaxBytes)

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
	handler := git.HandleGetPRStatus(fake, state, testMaxBytes)

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
	state := &fakeSessionState{}
	tool := mcp.NewTool("wait_for_gate",
		mcp.WithNumber("pr_number", mcp.Required()),
		mcp.WithNumber("timeout_seconds"),
	)
	handler := git.HandleWaitForGate(fake, state, testMaxBytes, time.Millisecond)
	result, err := callHandler(t, "wait_for_gate", tool, handler, map[string]any{
		"pr_number": float64(42),
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success (merged), got error: %v", result.Content)
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "gate passed") {
		t.Errorf("expected gate passed in response, got: %s", text)
	}
}

func TestWaitForGateHandler_DomainError(t *testing.T) {
	fake := &fakeGitClient{err: fmt.Errorf("API unreachable")}
	state := &fakeSessionState{}
	tool := mcp.NewTool("wait_for_gate",
		mcp.WithNumber("pr_number", mcp.Required()),
		mcp.WithNumber("timeout_seconds"),
	)
	handler := git.HandleWaitForGate(fake, state, testMaxBytes, time.Millisecond)

	result, err := callHandler(t, "wait_for_gate", tool, handler, map[string]any{
		"pr_number":       float64(42),
		"timeout_seconds": float64(30),
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for domain error on poll")
	}
}

func TestWaitForGateHandler_TimeoutRespected(t *testing.T) {
	fake := &fakeGitClient{prState: "open", prMerged: false}
	state := &fakeSessionState{}
	tool := mcp.NewTool("wait_for_gate",
		mcp.WithNumber("pr_number", mcp.Required()),
		mcp.WithNumber("timeout_seconds"),
	)
	handler := git.HandleWaitForGate(fake, state, testMaxBytes, time.Millisecond)

	start := time.Now()
	result, err := callHandler(t, "wait_for_gate", tool, handler, map[string]any{
		"pr_number":       float64(42),
		"timeout_seconds": float64(1),
	})
	elapsed := time.Since(start)

	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true on timeout")
	}
	const maxWallSeconds = 3
	if elapsed > maxWallSeconds*time.Second {
		t.Errorf("handler took %v, expected < %ds", elapsed, maxWallSeconds)
	}
}

func TestWaitForGateHandler_MissingArgument(t *testing.T) {
	fake := &fakeGitClient{}
	state := &fakeSessionState{}
	tool := mcp.NewTool("wait_for_gate",
		mcp.WithNumber("pr_number", mcp.Required()),
		mcp.WithNumber("timeout_seconds"),
	)
	handler := git.HandleWaitForGate(fake, state, testMaxBytes, time.Millisecond)

	result, err := callHandler(t, "wait_for_gate", tool, handler, map[string]any{})
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
	state := &fakeSessionState{}
	tool := mcp.NewTool("wait_for_gate",
		mcp.WithNumber("pr_number", mcp.Required()),
		mcp.WithNumber("timeout_seconds"),
	)
	handler := git.HandleWaitForGate(fake, state, testMaxBytes, time.Millisecond)

	result, err := callHandler(t, "wait_for_gate", tool, handler, map[string]any{
		"pr_number":       float64(42),
		"timeout_seconds": float64(30),
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true when gate check failed")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "gate check failed") {
		t.Errorf("expected 'gate check failed' in error, got: %s", text)
	}
	if !strings.Contains(text, "failure") {
		t.Errorf("expected conclusion in error, got: %s", text)
	}
}

func TestRevertCommitHandler_Success(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{revertSHA: "cafebabe"}
	state := preloadedState(cloneDir, "remediation/run-001")
	state.SetBaseBranch("main")
	tool := mcp.NewTool("revert_commit", mcp.WithString("merge_commit_sha", mcp.Required()))
	handler := git.HandleRevertCommit(fake, state, testMaxBytes)

	result, err := callHandler(t, "revert_commit", tool, handler, map[string]any{
		"merge_commit_sha": "deadbeef",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if result.IsError {
		t.Errorf("expected success, got error: %v", result.Content)
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "cafebabe") {
		t.Errorf("expected revert SHA in response, got: %s", text)
	}
}

func TestRevertCommitHandler_DomainError(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{err: fmt.Errorf("revert conflict")}
	state := preloadedState(cloneDir, "remediation/run-001")
	tool := mcp.NewTool("revert_commit", mcp.WithString("merge_commit_sha", mcp.Required()))
	handler := git.HandleRevertCommit(fake, state, testMaxBytes)

	result, err := callHandler(t, "revert_commit", tool, handler, map[string]any{
		"merge_commit_sha": "deadbeef",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for domain error")
	}
}

func TestRevertCommitHandler_InvalidSHA(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{}
	state := preloadedState(cloneDir, "remediation/run-001")
	tool := mcp.NewTool("revert_commit", mcp.WithString("merge_commit_sha", mcp.Required()))
	handler := git.HandleRevertCommit(fake, state, testMaxBytes)

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
	handler := git.HandleClosePR(fake, state, testMaxBytes)

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
	handler := git.HandleClosePR(fake, state, testMaxBytes)

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
	handler := git.HandleClosePR(fake, state, testMaxBytes)

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
	handler := git.HandleDeleteBranch(fake, state, testMaxBytes)

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
	handler := git.HandleDeleteBranch(fake, state, testMaxBytes)

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
	handler := git.HandleDeleteBranch(fake, state, testMaxBytes)

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
		t.Error("expected IsError=true when session not initialised and no authURL")
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
	fake := &fakeGitClient{revertSHA: "cafebabe"}
	state := preloadedState(cloneDir, "remediation/run-001")
	state.SetBaseBranch("chore/eval-cluster-baseline")

	tool := mcp.NewTool("revert_commit", mcp.WithString("merge_commit_sha", mcp.Required()))
	handler := git.HandleRevertCommit(fake, state, testMaxBytes)

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
	branch, _ := state.Branch()
	if branch != "chore/eval-cluster-baseline" {
		t.Errorf("expected session branch %q after revert, got %q", "chore/eval-cluster-baseline", branch)
	}
}

func TestHandleRevertCommit_FailsWhenBaseBranchUnset(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{revertSHA: "cafebabe"}
	state := preloadedState(cloneDir, "remediation/run-001")

	tool := mcp.NewTool("revert_commit", mcp.WithString("merge_commit_sha", mcp.Required()))
	handler := git.HandleRevertCommit(fake, state, testMaxBytes)

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

func TestRealGitClient_RevertCommitCheckoutMessage(t *testing.T) {
	repoDir := t.TempDir()
	if out, err := exec.Command("git", "-C", repoDir, "init").CombinedOutput(); err != nil {
		t.Fatalf("git init: %v: %s", err, out)
	}
	if out, err := exec.Command("git", "-C", repoDir, "config", "user.email", "test@test.com").CombinedOutput(); err != nil {
		t.Fatalf("git config email: %v: %s", err, out)
	}
	if out, err := exec.Command("git", "-C", repoDir, "config", "user.name", "test").CombinedOutput(); err != nil {
		t.Fatalf("git config name: %v: %s", err, out)
	}
	if err := os.WriteFile(filepath.Join(repoDir, "init.txt"), []byte("init"), 0o644); err != nil {
		t.Fatalf("write init: %v", err)
	}
	if out, err := exec.Command("git", "-C", repoDir, "add", ".").CombinedOutput(); err != nil {
		t.Fatalf("git add: %v: %s", err, out)
	}
	if out, err := exec.Command("git", "-C", repoDir, "commit", "-m", "init").CombinedOutput(); err != nil {
		t.Fatalf("git commit: %v: %s", err, out)
	}

	cfg := &config.Config{
		GitHubToken: "tok",
		RepoURL:     "https://github.com/x/y.git",
	}
	client := git.NewRealGitClient(cfg)

	_, err := client.RevertCommit(context.Background(), repoDir, "deadbeef", "chore/eval-cluster-baseline")
	if err == nil {
		t.Fatal("expected error for non-existent branch, got nil")
	}
	if !strings.Contains(err.Error(), "chore/eval-cluster-baseline") {
		t.Errorf("expected branch name in error message, got: %v", err)
	}
	if strings.Contains(err.Error(), ": checkout main:") {
		t.Errorf("error message must not contain 'checkout main:', got: %v", err)
	}
}
