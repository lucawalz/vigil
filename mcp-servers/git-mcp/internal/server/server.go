package server

import (
	"context"
	"sync"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"

	"github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/config"
	"github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/git"
)

type GitServer struct {
	mu            sync.Mutex
	currentBranch string
	lastCommitSHA string
	runID         string
	cloneDir      string
}

func NewServer(client git.GitClient, cfg *config.Config) *server.MCPServer {
	_ = client
	_ = cfg
	s := &GitServer{}
	_ = s

	mcpServer := server.NewMCPServer("git-mcp", "1.0.0",
		server.WithToolCapabilities(true),
	)

	mcpServer.AddTool(
		mcp.NewTool("create_branch",
			mcp.WithDescription("Create a remediation branch for the given run"),
			mcp.WithString("run_id",
				mcp.Required(),
				mcp.Description("Run identifier; must match ^[a-zA-Z0-9-]+$"),
			),
		),
		func(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			return mcp.NewToolResultError("handler not wired: create_branch"), nil
		},
	)

	mcpServer.AddTool(
		mcp.NewTool("write_manifest",
			mcp.WithDescription("Write a manifest file into the remediation branch"),
			mcp.WithString("manifest_path",
				mcp.Required(),
				mcp.Description("Repo-relative manifest path"),
			),
			mcp.WithString("patch_body",
				mcp.Required(),
				mcp.Description("Full replacement manifest YAML"),
			),
		),
		func(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			return mcp.NewToolResultError("handler not wired: write_manifest"), nil
		},
	)

	mcpServer.AddTool(
		mcp.NewTool("commit_files",
			mcp.WithDescription("Commit staged changes to the remediation branch"),
			mcp.WithString("message",
				mcp.Required(),
				mcp.Description("Commit message"),
			),
		),
		func(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			return mcp.NewToolResultError("handler not wired: commit_files"), nil
		},
	)

	mcpServer.AddTool(
		mcp.NewTool("push_branch",
			mcp.WithDescription("Push the remediation branch to origin"),
		),
		func(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			return mcp.NewToolResultError("handler not wired: push_branch"), nil
		},
	)

	mcpServer.AddTool(
		mcp.NewTool("create_pr",
			mcp.WithDescription("Open a pull request from the remediation branch"),
			mcp.WithString("title",
				mcp.Required(),
				mcp.Description("Pull request title"),
			),
			mcp.WithString("body",
				mcp.Required(),
				mcp.Description("Pull request description"),
			),
			mcp.WithString("base",
				mcp.Required(),
				mcp.Description("Base branch (default: main)"),
			),
		),
		func(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			return mcp.NewToolResultError("handler not wired: create_pr"), nil
		},
	)

	mcpServer.AddTool(
		mcp.NewTool("get_pr_status",
			mcp.WithDescription("Get the current status of a pull request"),
			mcp.WithNumber("pr_number",
				mcp.Required(),
				mcp.Description("Pull request number"),
			),
		),
		func(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			return mcp.NewToolResultError("handler not wired: get_pr_status"), nil
		},
	)

	mcpServer.AddTool(
		mcp.NewTool("wait_for_gate",
			mcp.WithDescription("Poll until the remediation PR is merged or fails the CI gate"),
			mcp.WithNumber("pr_number",
				mcp.Required(),
				mcp.Description("Pull request number"),
			),
			mcp.WithNumber("timeout_seconds",
				mcp.Description("Default 540"),
			),
		),
		func(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			return mcp.NewToolResultError("handler not wired: wait_for_gate"), nil
		},
	)

	mcpServer.AddTool(
		mcp.NewTool("revert_commit",
			mcp.WithDescription("Revert a merged remediation commit on main"),
			mcp.WithString("merge_commit_sha",
				mcp.Required(),
				mcp.Description("SHA of the merge commit to revert"),
			),
		),
		func(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			return mcp.NewToolResultError("handler not wired: revert_commit"), nil
		},
	)

	return mcpServer
}
