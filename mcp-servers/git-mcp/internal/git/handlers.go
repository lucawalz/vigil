package git

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
)

const (
	branchPrefix                     = "remediation/run-"
	pollIntervalSeconds              = 15
	defaultWaitForGateTimeoutSeconds = 480
)

const DefaultPollInterval = pollIntervalSeconds * time.Second

const (
	hintCloneRepo        = "verify the repo URL is accessible and the auth token has read permissions"
	hintCreateBranch     = "verify the base branch exists and the auth token has write permissions"
	hintWriteManifest    = "read the file with read_file first to confirm the path exists on the branch"
	hintCommitFiles      = "ensure write_manifest was called with valid content before committing"
	hintPushBranch       = "verify the auth token has push permissions to the remote"
	hintCreatePR         = "ensure push_branch succeeded and the branch exists on the remote"
	hintEnableAutoMerge  = "auto-merge may require branch protection rules; verify repo settings"
	hintGetPRStatus      = "verify the PR number was returned by create_pull_request"
	hintWaitForGate      = "check PR status with get_pr_status; the PR may have been closed or a CI check failed"
	hintClosePR          = "verify the PR number is correct; it may already be closed"
	hintDeleteBranch     = "verify the branch exists and is not protected"
	hintReadFile         = "verify the branch and path are correct; call resolve_manifest_path to locate the repo-relative path"
	hintReadFileNotFound = "call resolve_manifest_path(kustomize_path, kind, name, namespace) to locate the correct repo-relative path"
	hintRevertCommit     = "verify the merge commit SHA from wait_for_gate and that the session is initialised"
)

var runIDPattern = regexp.MustCompile(`^[a-zA-Z0-9_-]+$`)

var commitSHAPattern = regexp.MustCompile(`^[a-f0-9]{7,40}$`)

type SessionState interface {
	BeginSession(runID, cloneDir string)
	Branch() (branch string, cloneDir string)
	SetBranch(branch string)
	BaseBranch() string
	SetBaseBranch(branch string)
	SetLastCommit(sha string)
	RunID() string
	CloneDir() string
}

func HandleCloneRepo(client GitClient, state SessionState, authURL string, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		runID, ok := args["run_id"].(string)
		if !ok || runID == "" {
			return mcp.NewToolResultError("run_id: missing or wrong type"), nil
		}
		if !runIDPattern.MatchString(runID) {
			return mcp.NewToolResultError("run_id: must match ^[a-zA-Z0-9_-]+$"), nil
		}

		if state.CloneDir() != "" {
			return mcp.NewToolResultText(truncateOutput("already initialised", maxBytes)), nil
		}

		base, _ := args["base_branch"].(string)
		if base == "" {
			base = defaultBaseBranch
		}

		cloneDir, err := client.Clone(ctx, authURL, base)
		if err != nil {
			return toolError("HandleCloneRepo", err.Error(), hintCloneRepo), nil
		}
		state.BeginSession(runID, cloneDir)
		state.SetBaseBranch(base)

		return mcp.NewToolResultText(truncateOutput("cloned: "+base, maxBytes)), nil
	}
}

func HandleCreateBranch(client GitClient, state SessionState, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		runID, ok := args["run_id"].(string)
		if !ok || runID == "" {
			return mcp.NewToolResultError("run_id: missing or wrong type"), nil
		}
		if !runIDPattern.MatchString(runID) {
			return mcp.NewToolResultError("run_id: must match ^[a-zA-Z0-9_-]+$"), nil
		}

		cloneDir := state.CloneDir()
		if cloneDir == "" {
			return mcp.NewToolResultError("HandleCreateBranch: session not initialised; call clone_repo first"), nil
		}

		branch := branchPrefix + runID
		if err := client.CreateBranch(ctx, cloneDir, branch); err != nil {
			return toolError("HandleCreateBranch", err.Error(), hintCreateBranch), nil
		}
		state.SetBranch(branch)

		if base, _ := args["base_branch"].(string); base != "" {
			state.SetBaseBranch(base)
		}

		return mcp.NewToolResultText(truncateOutput("branch created: "+branch, maxBytes)), nil
	}
}

type runtimeFieldRule struct {
	name    string
	pattern *regexp.Regexp
}

var runtimeOnlyFieldRules = []runtimeFieldRule{
	{"metadata.creationTimestamp", regexp.MustCompile(`(?m)^  creationTimestamp:`)},
	{"metadata.resourceVersion", regexp.MustCompile(`(?m)^  resourceVersion:`)},
	{"metadata.uid", regexp.MustCompile(`(?m)^  uid:`)},
	{"metadata.generation", regexp.MustCompile(`(?m)^  generation:`)},
	{"metadata.managedFields", regexp.MustCompile(`(?m)^  managedFields:`)},
	{"status", regexp.MustCompile(`(?m)^status:`)},
}

func findRuntimeOnlyField(yamlBody string) string {
	for _, rule := range runtimeOnlyFieldRules {
		if rule.pattern.MatchString(yamlBody) {
			return rule.name
		}
	}
	return ""
}

// If nix-instantiate is missing, the error surfaces to the caller; a misconfigured host must not silently allow writes.
func validateNixSyntax(ctx context.Context, content string) error {
	tmp, err := os.CreateTemp("", "vigil-nix-*.nix")
	if err != nil {
		return fmt.Errorf("create temp file: %w", err)
	}
	defer func() { _ = os.Remove(tmp.Name()) }()
	if _, err := tmp.WriteString(content); err != nil {
		_ = tmp.Close()
		return fmt.Errorf("write temp file: %w", err)
	}
	_ = tmp.Close()
	cmd := exec.CommandContext(ctx, "nix-instantiate", "--parse", tmp.Name())
	if out, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("%s", strings.TrimSpace(string(out)))
	}
	return nil
}

func HandleWriteManifest(client GitClient, state SessionState, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		manifestPath, ok := args["manifest_path"].(string)
		if !ok || manifestPath == "" {
			return mcp.NewToolResultError("manifest_path: missing or wrong type"), nil
		}
		patchBody, ok := args["patch_body"].(string)
		if !ok || patchBody == "" {
			return mcp.NewToolResultError("patch_body: missing or wrong type"), nil
		}

		if strings.HasPrefix(manifestPath, "/") {
			return mcp.NewToolResultError("manifest_path: absolute paths are not allowed"), nil
		}
		cleaned := filepath.Clean(manifestPath)
		if cleaned == ".." || strings.HasPrefix(cleaned, ".."+string(filepath.Separator)) {
			return mcp.NewToolResultError("manifest_path: path traversal rejected"), nil
		}
		cloneDir := state.CloneDir()
		if cloneDir == "" {
			return mcp.NewToolResultError("HandleWriteManifest: session not initialised; call create_branch first"), nil
		}
		absPath := filepath.Join(cloneDir, cleaned)
		if !strings.HasPrefix(absPath, cloneDir+string(filepath.Separator)) {
			return mcp.NewToolResultError("manifest_path: path traversal rejected"), nil
		}

		existing, err := os.ReadFile(absPath)
		if err != nil {
			if os.IsNotExist(err) {
				return mcp.NewToolResultError("manifest_path: file does not exist on base branch; remediation cannot create new manifests"), nil
			}
			return toolError("HandleWriteManifest", "read existing: "+err.Error(), hintWriteManifest), nil
		}
		if string(existing) == patchBody {
			return mcp.NewToolResultError("patch_body: identical to current file; no-op patches are rejected"), nil
		}
		if strings.HasSuffix(cleaned, ".nix") {
			if err := validateNixSyntax(ctx, patchBody); err != nil {
				return mcp.NewToolResultError("patch_body: nix syntax error: " + err.Error()), nil
			}
		} else {
			if violation := findRuntimeOnlyField(patchBody); violation != "" {
				return mcp.NewToolResultError("patch_body: contains runtime-only field '" + violation + "'; submit a declarative manifest, not live cluster YAML"), nil
			}
		}

		if err := client.WriteFile(ctx, cloneDir, cleaned, patchBody); err != nil {
			return toolError("HandleWriteManifest", err.Error(), hintWriteManifest), nil
		}
		return mcp.NewToolResultText(truncateOutput("wrote manifest: "+manifestPath, maxBytes)), nil
	}
}

func HandleCommitFiles(client GitClient, state SessionState, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		message, ok := args["message"].(string)
		if !ok || message == "" {
			return mcp.NewToolResultError("message: missing or wrong type"), nil
		}

		branch, cloneDir := state.Branch()
		if branch == "" || cloneDir == "" {
			return mcp.NewToolResultError("HandleCommitFiles: session not initialised; call create_branch first"), nil
		}

		sha, err := client.CommitFiles(ctx, cloneDir, branch, message)
		if err != nil {
			return toolError("HandleCommitFiles", err.Error(), hintCommitFiles), nil
		}
		state.SetLastCommit(sha)
		return mcp.NewToolResultText(truncateOutput("commit: "+sha, maxBytes)), nil
	}
}

func HandlePushBranch(client GitClient, state SessionState, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		branch, cloneDir := state.Branch()
		if branch == "" || cloneDir == "" {
			return mcp.NewToolResultError("HandlePushBranch: session not initialised; call create_branch first"), nil
		}

		if err := client.Push(ctx, cloneDir, branch); err != nil {
			return toolError("HandlePushBranch", err.Error(), hintPushBranch), nil
		}
		return mcp.NewToolResultText(truncateOutput("pushed: "+branch, maxBytes)), nil
	}
}

func HandleCreatePR(client GitClient, state SessionState, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		title, ok := args["title"].(string)
		if !ok || title == "" {
			return mcp.NewToolResultError("title: missing or wrong type"), nil
		}
		body, ok := args["body"].(string)
		if !ok || body == "" {
			return mcp.NewToolResultError("body: missing or wrong type"), nil
		}
		base := state.BaseBranch()
		if base == "" {
			return mcp.NewToolResultError("HandleCreatePR: base branch not set; call clone_repo first"), nil
		}

		branch, _ := state.Branch()
		if branch == "" {
			return mcp.NewToolResultError("HandleCreatePR: session not initialised; call create_branch first"), nil
		}

		prNumber, err := client.CreatePR(ctx, title, branch, base, body)
		if err != nil {
			return toolError("HandleCreatePR", err.Error(), hintCreatePR), nil
		}
		if err := client.EnableAutoMerge(ctx, prNumber); err != nil {
			return toolError("HandleCreatePR", "enable auto-merge: "+err.Error(), hintEnableAutoMerge), nil
		}
		return mcp.NewToolResultText(truncateOutput(fmt.Sprintf("pr created: #%d", prNumber), maxBytes)), nil
	}
}

func HandleGetPRStatus(client GitClient, state SessionState, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		prNumF, ok := args["pr_number"].(float64)
		if !ok {
			return mcp.NewToolResultError("pr_number: missing or wrong type"), nil
		}
		prNumber := int(prNumF)

		prState, merged, mergeCommitSHA, err := client.GetPRStatus(ctx, prNumber)
		if err != nil {
			return toolError("HandleGetPRStatus", err.Error(), hintGetPRStatus), nil
		}
		output := fmt.Sprintf("%s merged=%v sha=%s", prState, merged, mergeCommitSHA)
		return mcp.NewToolResultText(truncateOutput(output, maxBytes)), nil
	}
}

func HandleWaitForGate(client GitClient, state SessionState, maxBytes int, pollInterval time.Duration) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		prNumF, ok := args["pr_number"].(float64)
		if !ok {
			return mcp.NewToolResultError("pr_number: missing or wrong type"), nil
		}
		prNumber := int(prNumF)

		timeoutSecs := defaultWaitForGateTimeoutSeconds
		if ts, ok := args["timeout_seconds"].(float64); ok && ts > 0 {
			timeoutSecs = int(ts)
		}

		timer := time.NewTimer(time.Duration(timeoutSecs) * time.Second)
		defer timer.Stop()
		ticker := time.NewTicker(pollInterval)
		defer ticker.Stop()

		for {
			select {
			case <-ctx.Done():
				return toolError("HandleWaitForGate", "context cancelled", hintWaitForGate), nil
			case <-timer.C:
				return toolError("HandleWaitForGate", fmt.Sprintf("timed out after %d seconds", timeoutSecs), hintWaitForGate), nil
			case <-ticker.C:
				prState, merged, mergeCommitSHA, err := client.GetPRStatus(ctx, prNumber)
				if err != nil {
					return toolError("HandleWaitForGate", err.Error(), hintWaitForGate), nil
				}
				if merged {
					output := fmt.Sprintf("gate passed: merged sha=%s", mergeCommitSHA)
					return mcp.NewToolResultText(truncateOutput(output, maxBytes)), nil
				}
				if prState == "closed" {
					return toolError("HandleWaitForGate", "PR closed without merge", hintWaitForGate), nil
				}
			}
		}
	}
}

func HandleClosePR(client GitClient, state SessionState, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		prNumF, ok := args["pr_number"].(float64)
		if !ok {
			return mcp.NewToolResultError("pr_number: missing or wrong type"), nil
		}
		prNumber := int(prNumF)
		if prNumber <= 0 {
			return mcp.NewToolResultError("pr_number: must be positive"), nil
		}

		if err := client.ClosePR(ctx, prNumber); err != nil {
			return toolError("HandleClosePR", err.Error(), hintClosePR), nil
		}
		return mcp.NewToolResultText(truncateOutput(fmt.Sprintf("pr #%d closed", prNumber), maxBytes)), nil
	}
}

func HandleDeleteBranch(client GitClient, state SessionState, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		branch, ok := args["branch"].(string)
		if !ok || branch == "" {
			return mcp.NewToolResultError("branch: missing or wrong type"), nil
		}

		if err := client.DeleteBranch(ctx, branch); err != nil {
			return toolError("HandleDeleteBranch", err.Error(), hintDeleteBranch), nil
		}
		return mcp.NewToolResultText(truncateOutput("branch deleted: "+branch, maxBytes)), nil
	}
}

func HandleReadFile(client GitClient, state SessionState, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		branch, ok := args["branch"].(string)
		if !ok || branch == "" {
			return mcp.NewToolResultError("branch: missing or wrong type"), nil
		}
		path, ok := args["path"].(string)
		if !ok || path == "" {
			return mcp.NewToolResultError("path: missing or wrong type"), nil
		}
		cloneDir := state.CloneDir()
		if cloneDir == "" {
			return mcp.NewToolResultError("HandleReadFile: session not initialised; call clone_repo first"), nil
		}
		contents, err := client.ReadFile(ctx, cloneDir, branch, path)
		if err != nil {
			hint := hintReadFile
			if strings.HasPrefix(err.Error(), "path not found:") {
				hint = hintReadFileNotFound
			}
			return toolError("HandleReadFile", err.Error(), hint), nil
		}
		return mcp.NewToolResultText(truncateOutput(contents, maxBytes)), nil
	}
}

func HandleResolveManifestPath(client GitClient, state SessionState, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		kustomizePath, ok := args["kustomize_path"].(string)
		if !ok || kustomizePath == "" {
			return mcp.NewToolResultError("kustomize_path: missing or wrong type"), nil
		}
		kind, ok := args["kind"].(string)
		if !ok || kind == "" {
			return mcp.NewToolResultError("kind: missing or wrong type"), nil
		}
		name, ok := args["name"].(string)
		if !ok || name == "" {
			return mcp.NewToolResultError("name: missing or wrong type"), nil
		}
		namespace, _ := args["namespace"].(string)

		cloneDir := state.CloneDir()
		if cloneDir == "" {
			return mcp.NewToolResultError("HandleResolveManifestPath: session not initialised; call clone_repo first"), nil
		}

		path, hint, err := client.ResolveManifestPath(ctx, cloneDir, kustomizePath, kind, namespace, name)
		if err != nil {
			return toolError("HandleResolveManifestPath", kind+"/"+name+" not found under "+kustomizePath, hint), nil
		}
		return mcp.NewToolResultText(truncateOutput(path, maxBytes)), nil
	}
}

func HandleRevertCommit(client GitClient, state SessionState, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		mergeCommitSHA, ok := args["merge_commit_sha"].(string)
		if !ok || mergeCommitSHA == "" {
			return mcp.NewToolResultError("merge_commit_sha: missing or wrong type"), nil
		}
		if !commitSHAPattern.MatchString(mergeCommitSHA) {
			return mcp.NewToolResultError("merge_commit_sha: must be a lowercase hex string (7–40 chars)"), nil
		}

		cloneDir := state.CloneDir()
		if cloneDir == "" {
			return mcp.NewToolResultError("HandleRevertCommit: session not initialised; call create_branch first"), nil
		}

		baseBranch := state.BaseBranch()
		if baseBranch == "" {
			return mcp.NewToolResultError("HandleRevertCommit: base branch not set; call clone_repo first"), nil
		}
		revertSHA, err := client.RevertCommit(ctx, cloneDir, mergeCommitSHA, baseBranch)
		if err != nil {
			return toolError("HandleRevertCommit", err.Error(), hintRevertCommit), nil
		}
		state.SetBranch(baseBranch)
		return mcp.NewToolResultText(truncateOutput("reverted: "+revertSHA, maxBytes)), nil
	}
}
