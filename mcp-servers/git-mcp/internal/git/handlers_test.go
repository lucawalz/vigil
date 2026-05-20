package git_test

import (
	"context"
	"errors"
	"fmt"
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
	cloneDir          string
	commitSHA         string
	prNumber          int
	prState           string
	prMerged          bool
	prMergeSHA        string
	revertSHA         string
	err               error
	getPRCalls        int
	autoMergeErr      error
	autoMergeCalls    int
	closePRErr        error
	closePRCalls      int
	deleteBranchErr   error
	deleteBranchCalls int
	readFileOut       string
	readFileErr       error
}

var _ git.GitClient = &fakeGitClient{}

func (f *fakeGitClient) Clone(_ context.Context, _ string) (string, error) {
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

func (f *fakeGitClient) CreatePR(_ context.Context, _, _, _, _ string) (int, error) {
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

func (f *fakeGitClient) RevertCommit(_ context.Context, _, _ string) (string, error) {
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

type fakeSessionState struct {
	mu            sync.Mutex
	runID         string
	cloneDir      string
	currentBranch string
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

func TestCreateBranchHandler_Success(t *testing.T) {
	fake := &fakeGitClient{cloneDir: t.TempDir()}
	state := &fakeSessionState{}
	tool := mcp.NewTool("create_branch", mcp.WithString("run_id", mcp.Required()))
	handler := git.HandleCreateBranch(fake, state, "https://x-access-token:tok@github.com/x/y.git", testMaxBytes)

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

func TestCreateBranchHandler_DomainError(t *testing.T) {
	fake := &fakeGitClient{err: fmt.Errorf("clone failed")}
	state := &fakeSessionState{}
	tool := mcp.NewTool("create_branch", mcp.WithString("run_id", mcp.Required()))
	handler := git.HandleCreateBranch(fake, state, "https://x-access-token:tok@github.com/x/y.git", testMaxBytes)

	result, err := callHandler(t, "create_branch", tool, handler, map[string]any{"run_id": "abc123"})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for domain error")
	}
}

func TestCreateBranchHandler_MissingArgument(t *testing.T) {
	fake := &fakeGitClient{cloneDir: t.TempDir()}
	state := &fakeSessionState{}
	tool := mcp.NewTool("create_branch", mcp.WithString("run_id", mcp.Required()))
	handler := git.HandleCreateBranch(fake, state, "", testMaxBytes)

	result, err := callHandler(t, "create_branch", tool, handler, map[string]any{})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for missing run_id")
	}
}

func TestCreateBranchHandler_RejectsInvalidRunID(t *testing.T) {
	fake := &fakeGitClient{cloneDir: t.TempDir()}
	state := &fakeSessionState{}
	tool := mcp.NewTool("create_branch", mcp.WithString("run_id", mcp.Required()))
	handler := git.HandleCreateBranch(fake, state, "", testMaxBytes)

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

func TestCreateBranchHandler_NoTokenInOutput(t *testing.T) {
	const sentinelToken = "SECRET_TOKEN_FIXTURE"
	cfg := &config.Config{
		GitHubToken:    sentinelToken,
		RepoURL:        "https://github.com/x/y.git",
		MaxOutputBytes: testMaxBytes,
	}
	fake := &fakeGitClient{cloneDir: t.TempDir()}
	state := &fakeSessionState{}
	tool := mcp.NewTool("create_branch", mcp.WithString("run_id", mcp.Required()))
	handler := git.HandleCreateBranch(fake, state, cfg.AuthURL(), testMaxBytes)

	result, err := callHandler(t, "create_branch", tool, handler, map[string]any{"run_id": "run-001"})
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

func TestWriteManifestHandler_Success(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{}
	state := preloadedState(cloneDir, "remediation/run-001")
	tool := mcp.NewTool("write_manifest",
		mcp.WithString("manifest_path", mcp.Required()),
		mcp.WithString("patch_body", mcp.Required()),
	)
	handler := git.HandleWriteManifest(fake, state, testMaxBytes)

	result, err := callHandler(t, "write_manifest", tool, handler, map[string]any{
		"manifest_path": "apps/deploy.yaml",
		"patch_body":    "apiVersion: apps/v1",
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
	tool := mcp.NewTool("create_pr",
		mcp.WithString("title", mcp.Required()),
		mcp.WithString("body", mcp.Required()),
		mcp.WithString("base", mcp.Required()),
	)
	handler := git.HandleCreatePR(fake, state, testMaxBytes)

	result, err := callHandler(t, "create_pr", tool, handler, map[string]any{
		"title": "fix: reduce OOMKilled replicas",
		"body":  "Automated remediation",
		"base":  "main",
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

func TestCreatePRHandler_DomainError(t *testing.T) {
	cloneDir := t.TempDir()
	fake := &fakeGitClient{err: fmt.Errorf("API error")}
	state := preloadedState(cloneDir, "remediation/run-001")
	tool := mcp.NewTool("create_pr",
		mcp.WithString("title", mcp.Required()),
		mcp.WithString("body", mcp.Required()),
		mcp.WithString("base", mcp.Required()),
	)
	handler := git.HandleCreatePR(fake, state, testMaxBytes)

	result, err := callHandler(t, "create_pr", tool, handler, map[string]any{
		"title": "fix: reduce replicas",
		"body":  "Remediation",
		"base":  "main",
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
	tool := mcp.NewTool("create_pr",
		mcp.WithString("title", mcp.Required()),
		mcp.WithString("body", mcp.Required()),
		mcp.WithString("base", mcp.Required()),
	)
	handler := git.HandleCreatePR(fake, state, testMaxBytes)

	result, err := callHandler(t, "create_pr", tool, handler, map[string]any{
		"title": "fix: reduce OOMKilled replicas",
		"body":  "Automated remediation",
		"base":  "main",
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
	tool := mcp.NewTool("create_pr",
		mcp.WithString("title", mcp.Required()),
		mcp.WithString("body", mcp.Required()),
		mcp.WithString("base", mcp.Required()),
	)
	handler := git.HandleCreatePR(fake, state, testMaxBytes)

	result, err := callHandler(t, "create_pr", tool, handler, map[string]any{"title": "t"})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true for missing body and base")
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

func TestRevertCommitHandler_Success(t *testing.T) {
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
	handler := git.HandleReadFile(fake, state, testMaxBytes)

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
	handler := git.HandleReadFile(fake, state, testMaxBytes)

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
	handler := git.HandleReadFile(fake, state, testMaxBytes)

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
	handler := git.HandleReadFile(fake, state, testMaxBytes)

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
	handler := git.HandleReadFile(fake, state, testMaxBytes)

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
	handler := git.HandleReadFile(fake, state, testMaxBytes)

	result, err := callHandler(t, "read_file", tool, handler, map[string]any{
		"branch": "chore/eval-cluster-baseline",
		"path":   "infra/k8s/cm.yaml",
	})
	if err != nil {
		t.Fatalf("CallTool error: %v", err)
	}
	if !result.IsError {
		t.Error("expected IsError=true when session not initialised")
	}
	text := result.Content[0].(mcp.TextContent).Text
	if !strings.Contains(text, "session not initialised") {
		t.Errorf("expected 'session not initialised' in error, got: %s", text)
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
