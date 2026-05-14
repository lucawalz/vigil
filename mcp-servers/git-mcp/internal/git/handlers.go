package git

import (
	"context"
	"fmt"
	"os"
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

		return mcp.NewToolResultText("branch created: " + branch), nil
	}
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
