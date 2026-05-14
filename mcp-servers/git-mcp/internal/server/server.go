package server

import (
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

func (s *GitServer) BeginSession(runID, cloneDir string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.runID = runID
	s.cloneDir = cloneDir
}

func (s *GitServer) Branch() (string, string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.currentBranch, s.cloneDir
}

func (s *GitServer) SetBranch(branch string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.currentBranch = branch
}

func (s *GitServer) SetLastCommit(sha string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.lastCommitSHA = sha
}

func (s *GitServer) RunID() string {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.runID
}

func (s *GitServer) CloneDir() string {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.cloneDir
}

func NewServer(client git.GitClient, cfg *config.Config) *server.MCPServer {
	s := &GitServer{}

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
		git.HandleCreateBranch(client, s, cfg.AuthURL(), cfg.MaxOutputBytes),
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
		git.HandleWriteManifest(client, s, cfg.MaxOutputBytes),
	)

	mcpServer.AddTool(
		mcp.NewTool("commit_files",
			mcp.WithDescription("Commit staged changes to the remediation branch"),
			mcp.WithString("message",
				mcp.Required(),
				mcp.Description("Commit message"),
			),
		),
		git.HandleCommitFiles(client, s, cfg.MaxOutputBytes),
	)

	mcpServer.AddTool(
		mcp.NewTool("push_branch",
			mcp.WithDescription("Push the remediation branch to origin"),
		),
		git.HandlePushBranch(client, s, cfg.MaxOutputBytes),
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
		git.HandleCreatePR(client, s, cfg.MaxOutputBytes),
	)

	mcpServer.AddTool(
		mcp.NewTool("get_pr_status",
			mcp.WithDescription("Get the current status of a pull request"),
			mcp.WithNumber("pr_number",
				mcp.Required(),
				mcp.Description("Pull request number"),
			),
		),
		git.HandleGetPRStatus(client, s, cfg.MaxOutputBytes),
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
		git.HandleWaitForGate(client, s, cfg.MaxOutputBytes),
	)

	mcpServer.AddTool(
		mcp.NewTool("revert_commit",
			mcp.WithDescription("Revert a merged remediation commit on main"),
			mcp.WithString("merge_commit_sha",
				mcp.Required(),
				mcp.Description("SHA of the merge commit to revert"),
			),
		),
		git.HandleRevertCommit(client, s, cfg.MaxOutputBytes),
	)

	return mcpServer
}
