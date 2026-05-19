package git

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	git "github.com/go-git/go-git/v5"
	gitconfig "github.com/go-git/go-git/v5/config"
	"github.com/go-git/go-git/v5/plumbing"
	"github.com/go-git/go-git/v5/plumbing/object"
	githttp "github.com/go-git/go-git/v5/plumbing/transport/http"
	gogithub "github.com/google/go-github/v86/github"
	"golang.org/x/oauth2"

	"github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/config"
)

const (
	commitAuthorName  = "vigil-remediation"
	commitAuthorEmail = "remediation@vigil.local"
	defaultBaseBranch = "main"
	gitAccessToken    = "x-access-token"
)

type GitClient interface {
	Clone(ctx context.Context, authURL string) (cloneDir string, err error)
	CreateBranch(ctx context.Context, cloneDir, branch string) error
	WriteFile(ctx context.Context, cloneDir, manifestPath, content string) error
	CommitFiles(ctx context.Context, cloneDir, branch, message string) (sha string, err error)
	Push(ctx context.Context, cloneDir, branch string) error
	CreatePR(ctx context.Context, title, head, base, body string) (prNumber int, err error)
	EnableAutoMerge(ctx context.Context, prNumber int) error
	GetPRStatus(ctx context.Context, prNumber int) (state string, merged bool, mergeCommitSHA string, err error)
	RevertCommit(ctx context.Context, cloneDir, mergeCommitSHA string) (revertSHA string, err error)
	ClosePR(ctx context.Context, prNumber int) error
	DeleteBranch(ctx context.Context, branch string) error
	ReadFile(ctx context.Context, cloneDir, branch, path string) (string, error)
}

type realGitClient struct {
	gh    *gogithub.Client
	cfg   *config.Config
	owner string
	repo  string
}

func NewRealGitClient(cfg *config.Config) GitClient {
	ts := oauth2.StaticTokenSource(&oauth2.Token{AccessToken: cfg.GitHubToken})
	httpClient := oauth2.NewClient(context.Background(), ts)
	gh := gogithub.NewClient(httpClient)

	owner, repo := parseRepoURL(cfg.RepoURL)
	return &realGitClient{
		gh:    gh,
		cfg:   cfg,
		owner: owner,
		repo:  repo,
	}
}

func parseRepoURL(repoURL string) (owner, repo string) {
	url := repoURL
	url = strings.TrimPrefix(url, "https://github.com/")
	url = strings.TrimSuffix(url, ".git")
	parts := strings.SplitN(url, "/", 2)
	if len(parts) != 2 || parts[0] == "" || parts[1] == "" {
		log.Fatalf("git-mcp: cannot parse REPO_URL %q — expected https://github.com/owner/repo.git", repoURL)
	}
	return parts[0], parts[1]
}

func sanitiseAuthError(err error, authURL string) error {
	if err == nil {
		return nil
	}
	msg := strings.ReplaceAll(err.Error(), authURL, "[redacted]")
	return fmt.Errorf("%s", msg) //nolint:err113
}

func (c *realGitClient) Clone(ctx context.Context, authURL string) (string, error) {
	dir, err := os.MkdirTemp("", "git-mcp-*")
	if err != nil {
		return "", fmt.Errorf("clone: create temp dir: %w", err)
	}
	if err := os.Chmod(dir, 0o700); err != nil {
		_ = os.RemoveAll(dir)
		return "", fmt.Errorf("clone: chmod temp dir: %w", err)
	}

	_, err = git.PlainCloneContext(ctx, dir, false, &git.CloneOptions{
		URL:          authURL,
		Depth:        1,
		SingleBranch: false,
	})
	if err != nil {
		_ = os.RemoveAll(dir)
		return "", sanitiseAuthError(fmt.Errorf("clone: %w", err), authURL)
	}
	return dir, nil
}

func (c *realGitClient) CreateBranch(_ context.Context, cloneDir, branch string) error {
	r, err := git.PlainOpen(cloneDir)
	if err != nil {
		return sanitiseAuthError(fmt.Errorf("create_branch: open repo: %w", err), c.cfg.AuthURL())
	}
	wt, err := r.Worktree()
	if err != nil {
		return sanitiseAuthError(fmt.Errorf("create_branch: worktree: %w", err), c.cfg.AuthURL())
	}
	err = wt.Checkout(&git.CheckoutOptions{
		Branch: plumbing.NewBranchReferenceName(branch),
		Create: true,
		Keep:   false,
	})
	if err != nil {
		return sanitiseAuthError(fmt.Errorf("create_branch: checkout: %w", err), c.cfg.AuthURL())
	}
	return nil
}

func (c *realGitClient) WriteFile(_ context.Context, cloneDir, manifestPath, content string) error {
	absPath := filepath.Join(cloneDir, manifestPath)
	if err := os.MkdirAll(filepath.Dir(absPath), 0o755); err != nil {
		return fmt.Errorf("write_file: mkdir: %w", err)
	}
	if err := os.WriteFile(absPath, []byte(content), 0o644); err != nil {
		return fmt.Errorf("write_file: write: %w", err)
	}
	return nil
}

func (c *realGitClient) CommitFiles(_ context.Context, cloneDir, _ string, message string) (string, error) {
	r, err := git.PlainOpen(cloneDir)
	if err != nil {
		return "", sanitiseAuthError(fmt.Errorf("commit_files: open repo: %w", err), c.cfg.AuthURL())
	}
	wt, err := r.Worktree()
	if err != nil {
		return "", sanitiseAuthError(fmt.Errorf("commit_files: worktree: %w", err), c.cfg.AuthURL())
	}
	if err := wt.AddGlob("."); err != nil {
		return "", sanitiseAuthError(fmt.Errorf("commit_files: add: %w", err), c.cfg.AuthURL())
	}
	hash, err := wt.Commit(message, &git.CommitOptions{
		Author: &object.Signature{
			Name:  commitAuthorName,
			Email: commitAuthorEmail,
			When:  time.Now(),
		},
	})
	if err != nil {
		return "", sanitiseAuthError(fmt.Errorf("commit_files: commit: %w", err), c.cfg.AuthURL())
	}
	return hash.String(), nil
}

func (c *realGitClient) Push(ctx context.Context, cloneDir, branch string) error {
	r, err := git.PlainOpen(cloneDir)
	if err != nil {
		return fmt.Errorf("push: open repo: %w", err)
	}
	refSpec := gitconfig.RefSpec(fmt.Sprintf("refs/heads/%s:refs/heads/%s", branch, branch))
	err = r.PushContext(ctx, &git.PushOptions{
		RemoteName: "origin",
		Auth: &githttp.BasicAuth{
			Username: gitAccessToken,
			Password: c.cfg.GitHubToken,
		},
		RefSpecs: []gitconfig.RefSpec{refSpec},
	})
	if err != nil && err != git.NoErrAlreadyUpToDate {
		return sanitiseAuthError(fmt.Errorf("push: %w", err), c.cfg.AuthURL())
	}
	return nil
}

func (c *realGitClient) CreatePR(ctx context.Context, title, head, base, body string) (int, error) {
	pr, _, err := c.gh.PullRequests.Create(ctx, c.owner, c.repo, &gogithub.NewPullRequest{
		Title: &title,
		Head:  &head,
		Base:  &base,
		Body:  &body,
	})
	if err != nil {
		return 0, fmt.Errorf("create_pr: %w", err)
	}
	return pr.GetNumber(), nil
}

func (c *realGitClient) EnableAutoMerge(ctx context.Context, prNumber int) error {
	pr, _, err := c.gh.PullRequests.Get(ctx, c.owner, c.repo, prNumber)
	if err != nil {
		return fmt.Errorf("enable_auto_merge: get pr: %w", err)
	}
	nodeID := pr.GetNodeID()
	if nodeID == "" {
		return fmt.Errorf("enable_auto_merge: PR #%d has no node_id", prNumber)
	}

	const mutation = `mutation($pullRequestId: ID!) {
		enablePullRequestAutoMerge(input: {
			pullRequestId: $pullRequestId,
			mergeMethod: SQUASH
		}) { pullRequest { id } }
	}`
	body, _ := json.Marshal(map[string]any{
		"query":     mutation,
		"variables": map[string]any{"pullRequestId": nodeID},
	})

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, "https://api.github.com/graphql", bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("enable_auto_merge: build request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.gh.Client().Do(req)
	if err != nil {
		return fmt.Errorf("enable_auto_merge: post: %w", err)
	}
	defer func() { _ = resp.Body.Close() }()

	respBody, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("enable_auto_merge: status %d: %s", resp.StatusCode, strings.TrimSpace(string(respBody)))
	}

	var gqlResp struct {
		Errors []struct{ Message string } `json:"errors"`
	}
	if json.Unmarshal(respBody, &gqlResp) == nil && len(gqlResp.Errors) > 0 {
		return fmt.Errorf("enable_auto_merge: graphql: %s", gqlResp.Errors[0].Message)
	}
	return nil
}

func (c *realGitClient) GetPRStatus(ctx context.Context, prNumber int) (string, bool, string, error) {
	pr, _, err := c.gh.PullRequests.Get(ctx, c.owner, c.repo, prNumber)
	if err != nil {
		return "", false, "", fmt.Errorf("get_pr_status: %w", err)
	}
	return pr.GetState(), pr.GetMerged(), pr.GetMergeCommitSHA(), nil
}

func (c *realGitClient) ClosePR(ctx context.Context, prNumber int) error {
	pr, _, err := c.gh.PullRequests.Get(ctx, c.owner, c.repo, prNumber)
	if err != nil {
		return fmt.Errorf("close_pr: get pr: %w", err)
	}
	branch := pr.GetHead().GetRef()

	closed := "closed"
	if _, _, err := c.gh.PullRequests.Edit(ctx, c.owner, c.repo, prNumber, &gogithub.PullRequest{State: &closed}); err != nil {
		return fmt.Errorf("close_pr: edit: %w", err)
	}
	if branch != "" {
		if _, err := c.gh.Git.DeleteRef(ctx, c.owner, c.repo, "refs/heads/"+branch); err != nil {
			return fmt.Errorf("close_pr: delete branch %s: %w", branch, err)
		}
	}
	return nil
}

func (c *realGitClient) DeleteBranch(ctx context.Context, branch string) error {
	if _, err := c.gh.Git.DeleteRef(ctx, c.owner, c.repo, "refs/heads/"+branch); err != nil {
		return fmt.Errorf("delete_branch: %w", err)
	}
	return nil
}

// go-git v5 does not expose a native Revert; fall back to the git binary.
func (c *realGitClient) RevertCommit(ctx context.Context, cloneDir, mergeCommitSHA string) (string, error) {
	r, err := git.PlainOpen(cloneDir)
	if err != nil {
		return "", sanitiseAuthError(fmt.Errorf("revert_commit: open repo: %w", err), c.cfg.AuthURL())
	}
	wt, err := r.Worktree()
	if err != nil {
		return "", sanitiseAuthError(fmt.Errorf("revert_commit: worktree: %w", err), c.cfg.AuthURL())
	}

	if err := wt.Checkout(&git.CheckoutOptions{
		Branch: plumbing.NewBranchReferenceName(defaultBaseBranch),
		Create: false,
	}); err != nil {
		return "", sanitiseAuthError(fmt.Errorf("revert_commit: checkout main: %w", err), c.cfg.AuthURL())
	}

	cmd := exec.CommandContext(ctx, "git", "-C", cloneDir, "revert", "--no-edit", mergeCommitSHA)
	if out, err := cmd.CombinedOutput(); err != nil {
		return "", sanitiseAuthError(fmt.Errorf("revert_commit: git revert: %w: %s", err, strings.TrimSpace(string(out))), c.cfg.AuthURL())
	}

	head, err := r.Head()
	if err != nil {
		return "", sanitiseAuthError(fmt.Errorf("revert_commit: read HEAD after revert: %w", err), c.cfg.AuthURL())
	}
	return head.Hash().String(), nil
}
