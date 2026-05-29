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
	baseBranch    string
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

func (s *GitServer) BaseBranch() string {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.baseBranch
}

func (s *GitServer) SetBaseBranch(branch string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.baseBranch = branch
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

const serverVersion = "1.0.0"

func NewServer(client git.GitClient, cfg *config.Config) *server.MCPServer {
	s := &GitServer{}

	mcpServer := server.NewMCPServer("git-mcp", serverVersion,
		server.WithToolCapabilities(true),
	)

	mcpServer.AddTool(
		mcp.NewTool("clone_repo",
			mcp.WithDescription("Clone the repository and initialise the git-mcp session; idempotent"),
			mcp.WithString("run_id",
				mcp.Required(),
				mcp.Description("Run identifier; must match ^[a-zA-Z0-9_-]+$"),
			),
			mcp.WithString("base_branch",
				mcp.Description("Branch to clone from (default: main)"),
			),
			mcp.WithOutputSchema[git.TextResult](),
		),
		git.HandleCloneRepo(client, s, cfg.AuthURL(), cfg.MaxOutputBytes),
	)

	mcpServer.AddTool(
		mcp.NewTool("create_branch",
			mcp.WithDescription("Create a remediation branch; requires a prior clone_repo call"),
			mcp.WithString("run_id",
				mcp.Required(),
				mcp.Description("Run identifier; must match ^[a-zA-Z0-9_-]+$"),
			),
			mcp.WithString("base_branch",
				mcp.Description("Override the base branch set by clone_repo"),
			),
			mcp.WithOutputSchema[git.TextResult](),
		),
		git.HandleCreateBranch(client, s, cfg.MaxOutputBytes),
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
			mcp.WithOutputSchema[git.TextResult](),
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
			mcp.WithOutputSchema[git.CommitResult](),
		),
		git.HandleCommitFiles(client, s),
	)

	mcpServer.AddTool(
		mcp.NewTool("push_branch",
			mcp.WithDescription("Push the remediation branch to origin"),
			mcp.WithOutputSchema[git.TextResult](),
		),
		git.HandlePushBranch(client, s, cfg.MaxOutputBytes),
	)

	mcpServer.AddTool(
		mcp.NewTool("create_pr",
			mcp.WithDescription("Open a pull request from the remediation branch into the cloned base branch"),
			mcp.WithString("title",
				mcp.Required(),
				mcp.Description("Pull request title"),
			),
			mcp.WithString("body",
				mcp.Required(),
				mcp.Description("Pull request description"),
			),
			mcp.WithOutputSchema[git.PRNumberResult](),
		),
		git.HandleCreatePR(client, s),
	)

	mcpServer.AddTool(
		mcp.NewTool("get_pr_status",
			mcp.WithDescription("Get the current status of a pull request"),
			mcp.WithNumber("pr_number",
				mcp.Required(),
				mcp.Description("Pull request number"),
			),
			mcp.WithOutputSchema[git.PRStatusResult](),
		),
		git.HandleGetPRStatus(client, s),
	)

	mcpServer.AddTool(
		mcp.NewTool("wait_for_gate",
			mcp.WithDescription("Poll until the remediation PR is merged or fails the CI gate"),
			mcp.WithNumber("pr_number",
				mcp.Required(),
				mcp.Description("Pull request number"),
			),
			mcp.WithNumber("timeout_seconds",
				mcp.Description("Default 480"),
			),
			mcp.WithOutputSchema[git.GatePassedResult](),
		),
		git.HandleWaitForGate(client, s, git.DefaultPollInterval),
	)

	mcpServer.AddTool(
		mcp.NewTool("revert_commit",
			mcp.WithDescription("Revert a merged remediation commit on main"),
			mcp.WithString("merge_commit_sha",
				mcp.Required(),
				mcp.Description("SHA of the merge commit to revert"),
			),
			mcp.WithOutputSchema[git.CommitResult](),
		),
		git.HandleRevertCommit(client, s),
	)

	mcpServer.AddTool(
		mcp.NewTool("close_pr",
			mcp.WithDescription("Close a pull request and delete its branch"),
			mcp.WithNumber("pr_number",
				mcp.Required(),
				mcp.Description("Pull request number"),
			),
			mcp.WithOutputSchema[git.PRNumberResult](),
		),
		git.HandleClosePR(client, s),
	)

	mcpServer.AddTool(
		mcp.NewTool("delete_branch",
			mcp.WithDescription("Delete a remote branch"),
			mcp.WithString("branch",
				mcp.Required(),
				mcp.Description("Branch name to delete"),
			),
			mcp.WithOutputSchema[git.TextResult](),
		),
		git.HandleDeleteBranch(client, s, cfg.MaxOutputBytes),
	)

	mcpServer.AddTool(
		mcp.NewTool("read_file",
			mcp.WithDescription("Read a file from the repository at a given branch tip; auto-initialises the session if needed"),
			mcp.WithString("branch", mcp.Required(), mcp.Description("Branch name to read from")),
			mcp.WithString("path", mcp.Required(), mcp.Description("Repo-relative file path")),
			mcp.WithOutputSchema[git.ReadFileResult](),
		),
		git.HandleReadFile(client, s, cfg.AuthURL(), cfg.MaxOutputBytes),
	)

	mcpServer.AddTool(
		mcp.NewTool("resolve_manifest_path",
			mcp.WithDescription("Walk the kustomize resource tree and return the repo-relative path to the manifest declaring the named resource"),
			mcp.WithString("kustomize_path",
				mcp.Required(),
				mcp.Description("Kustomization spec.path value (repo-relative directory, e.g. infra/overlays/hetzner/kubernetes/clusters/hetzner)"),
			),
			mcp.WithString("kind",
				mcp.Required(),
				mcp.Description("Kubernetes resource kind, e.g. Deployment"),
			),
			mcp.WithString("name",
				mcp.Required(),
				mcp.Description("Resource name"),
			),
			mcp.WithString("namespace",
				mcp.Description("Resource namespace (default: default)"),
			),
			mcp.WithOutputSchema[git.ManifestPathResult](),
		),
		git.HandleResolveManifestPath(client, s),
	)

	return mcpServer
}
