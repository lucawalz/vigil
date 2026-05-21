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
	defaultWaitForGateTimeoutSeconds = 540
)

const DefaultPollInterval = pollIntervalSeconds * time.Second

var runIDPattern = regexp.MustCompile(`^[a-zA-Z0-9-]+$`)

var commitSHAPattern = regexp.MustCompile(`^[a-f0-9]{7,40}$`)

type SessionState interface {
	BeginSession(runID, cloneDir string)
	Branch() (branch string, cloneDir string)
	SetBranch(branch string)
	SetLastCommit(sha string)
	RunID() string
	CloneDir() string
}

func HandleCreateBranch(client GitClient, state SessionState, authURL string, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		runID, ok := args["run_id"].(string)
		if !ok || runID == "" {
			return mcp.NewToolResultError("run_id: missing or wrong type"), nil
		}
		if !runIDPattern.MatchString(runID) {
			return mcp.NewToolResultError("run_id: must match ^[a-zA-Z0-9-]+$"), nil
		}

		cloneDir, err := client.Clone(ctx, authURL)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("HandleCreateBranch: %v", err)), nil
		}

		branch := branchPrefix + runID
		if err := client.CreateBranch(ctx, cloneDir, branch); err != nil {
			_ = os.RemoveAll(cloneDir)
			return mcp.NewToolResultError(fmt.Sprintf("HandleCreateBranch: %v", err)), nil
		}
		state.BeginSession(runID, cloneDir)
		state.SetBranch(branch)

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
	defer os.Remove(tmp.Name())
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
			return mcp.NewToolResultError(fmt.Sprintf("HandleWriteManifest: read existing: %v", err)), nil
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
			return mcp.NewToolResultError(fmt.Sprintf("HandleWriteManifest: %v", err)), nil
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
			return mcp.NewToolResultError(fmt.Sprintf("HandleCommitFiles: %v", err)), nil
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
			return mcp.NewToolResultError(fmt.Sprintf("HandlePushBranch: %v", err)), nil
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
		base, ok := args["base"].(string)
		if !ok || base == "" {
			return mcp.NewToolResultError("base: missing or wrong type"), nil
		}

		branch, _ := state.Branch()
		if branch == "" {
			return mcp.NewToolResultError("HandleCreatePR: session not initialised; call create_branch first"), nil
		}

		prNumber, err := client.CreatePR(ctx, title, branch, base, body)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("HandleCreatePR: %v", err)), nil
		}
		if err := client.EnableAutoMerge(ctx, prNumber); err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("HandleCreatePR: enable auto-merge: %v", err)), nil
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
			return mcp.NewToolResultError(fmt.Sprintf("HandleGetPRStatus: %v", err)), nil
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
				return mcp.NewToolResultError("HandleWaitForGate: context cancelled"), nil
			case <-timer.C:
				return mcp.NewToolResultError(fmt.Sprintf("HandleWaitForGate: timed out after %d seconds", timeoutSecs)), nil
			case <-ticker.C:
				prState, merged, mergeCommitSHA, err := client.GetPRStatus(ctx, prNumber)
				if err != nil {
					return mcp.NewToolResultError(fmt.Sprintf("HandleWaitForGate: %v", err)), nil
				}
				if merged {
					output := fmt.Sprintf("gate passed: merged sha=%s", mergeCommitSHA)
					return mcp.NewToolResultText(truncateOutput(output, maxBytes)), nil
				}
				if prState == "closed" {
					return mcp.NewToolResultError("HandleWaitForGate: PR closed without merge"), nil
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
			return mcp.NewToolResultError(fmt.Sprintf("HandleClosePR: %v", err)), nil
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
			return mcp.NewToolResultError(fmt.Sprintf("HandleDeleteBranch: %v", err)), nil
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
			return mcp.NewToolResultError("HandleReadFile: session not initialised; call create_branch first"), nil
		}
		contents, err := client.ReadFile(ctx, cloneDir, branch, path)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("HandleReadFile: %v", err)), nil
		}
		return mcp.NewToolResultText(truncateOutput(contents, maxBytes)), nil
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

		revertSHA, err := client.RevertCommit(ctx, cloneDir, mergeCommitSHA)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("HandleRevertCommit: %v", err)), nil
		}
		state.SetBranch(defaultBaseBranch)
		return mcp.NewToolResultText(truncateOutput("reverted: "+revertSHA, maxBytes)), nil
	}
}
