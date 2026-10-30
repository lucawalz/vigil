package git

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"errors"
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

	"github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/auth"
	"github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/config"
)

const (
	defaultBaseBranch = "main"
	gitAccessToken    = "x-access-token"
	redacted          = "[redacted]"
)

type GitClient interface {
	Clone(ctx context.Context, repoURL, baseBranch string) (cloneDir string, err error)
	CreateBranch(ctx context.Context, cloneDir, branch, baseBranch string) error
	WriteFile(ctx context.Context, cloneDir, manifestPath, content string) error
	CommitFiles(ctx context.Context, cloneDir, branch, message string) (sha string, err error)
	Push(ctx context.Context, cloneDir, branch string) error
	CreatePR(ctx context.Context, title, head, base, body string) (prNumber int, err error)
	EnableAutoMerge(ctx context.Context, prNumber int) error
	DisableAutoMerge(ctx context.Context, prNumber int) error
	GetPRStatus(ctx context.Context, prNumber int) (state string, merged bool, mergeCommitSHA string, err error)
	GetCheckRunStatus(ctx context.Context, prNumber int) (gateFailed bool, conclusion string, err error)
	GetMergeableState(ctx context.Context, prNumber int) (string, error)
	RevertCommit(ctx context.Context, cloneDir, mergeCommitSHA, baseBranch, revertBranch string) (revertSHA string, err error)
	ClosePR(ctx context.Context, prNumber int) error
	DeleteBranch(ctx context.Context, branch string) error
	ReadFile(ctx context.Context, cloneDir, branch, path string) (string, error)
	ResolveManifestPath(ctx context.Context, cloneDir, kustomizePath, kind, namespace, name string) (repoRelPath string, hint string, err error)
}

type realGitClient struct {
	gh    *gogithub.Client
	id    auth.Identity
	owner string
	repo  string
}

func NewRealGitClient(cfg *config.Config, id auth.Identity) GitClient {
	owner, repo, err := cfg.Repository()
	if err != nil {
		log.Fatalf("git-mcp: %v", err)
	}
	return &realGitClient{
		gh:    gogithub.NewClient(id.Token.HTTPClient()),
		id:    id,
		owner: owner,
		repo:  repo,
	}
}

func sanitiseAuthError(err error, token string) error {
	if err == nil || token == "" {
		return err
	}
	msg := strings.NewReplacer(token, redacted, basicCredentials(token), redacted).Replace(err.Error())
	return fmt.Errorf("%s", msg) //nolint:err113
}

func basicCredentials(token string) string {
	return base64.StdEncoding.EncodeToString([]byte(gitAccessToken + ":" + token))
}

func (c *realGitClient) basicAuth(ctx context.Context) (*githttp.BasicAuth, error) {
	token, err := c.id.Token(ctx)
	if err != nil {
		return nil, fmt.Errorf("github token: %w", err)
	}
	return &githttp.BasicAuth{Username: gitAccessToken, Password: token}, nil
}

func (c *realGitClient) Clone(ctx context.Context, repoURL, baseBranch string) (string, error) {
	basicAuth, err := c.basicAuth(ctx)
	if err != nil {
		return "", fmt.Errorf("clone: %w", err)
	}
	dir, err := os.MkdirTemp("", "git-mcp-*")
	if err != nil {
		return "", fmt.Errorf("clone: create temp dir: %w", err)
	}
	if err := os.Chmod(dir, 0o700); err != nil {
		_ = os.RemoveAll(dir)
		return "", fmt.Errorf("clone: chmod temp dir: %w", err)
	}

	opts := &git.CloneOptions{
		URL:          repoURL,
		Auth:         basicAuth,
		Depth:        1,
		SingleBranch: false,
	}
	if baseBranch != "" {
		opts.ReferenceName = plumbing.NewBranchReferenceName(baseBranch)
	}
	_, err = git.PlainCloneContext(ctx, dir, false, opts)
	if err != nil {
		_ = os.RemoveAll(dir)
		return "", sanitiseAuthError(fmt.Errorf("clone: %w", err), basicAuth.Password)
	}
	return dir, nil
}

func (c *realGitClient) CreateBranch(ctx context.Context, cloneDir, branch, baseBranch string) error {
	if baseBranch == "" {
		baseBranch = defaultBaseBranch
	}
	r, err := git.PlainOpen(cloneDir)
	if err != nil {
		return fmt.Errorf("create_branch: open repo: %w", err)
	}
	wt, err := r.Worktree()
	if err != nil {
		return fmt.Errorf("create_branch: worktree: %w", err)
	}

	basicAuth, err := c.basicAuth(ctx)
	if err != nil {
		return fmt.Errorf("create_branch: %w", err)
	}
	fetchErr := r.FetchContext(ctx, &git.FetchOptions{
		RefSpecs: []gitconfig.RefSpec{
			gitconfig.RefSpec("refs/heads/" + baseBranch + ":refs/remotes/origin/" + baseBranch),
		},
		Auth: basicAuth,
	})
	if fetchErr != nil && !errors.Is(fetchErr, git.NoErrAlreadyUpToDate) {
		return sanitiseAuthError(fmt.Errorf("create_branch: fetch base %s: %w", baseBranch, fetchErr), basicAuth.Password)
	}

	ref, err := r.Reference(plumbing.NewRemoteReferenceName("origin", baseBranch), true)
	if err != nil {
		return fmt.Errorf("create_branch: resolve base %s: %w", baseBranch, err)
	}

	if err := wt.Reset(&git.ResetOptions{Mode: git.HardReset, Commit: ref.Hash()}); err != nil {
		return fmt.Errorf("create_branch: reset to base %s: %w", baseBranch, err)
	}

	if err := wt.Checkout(&git.CheckoutOptions{
		Branch: plumbing.NewBranchReferenceName(branch),
		Create: true,
		Keep:   false,
	}); err != nil {
		return fmt.Errorf("create_branch: checkout: %w", err)
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
		return "", fmt.Errorf("commit_files: open repo: %w", err)
	}
	wt, err := r.Worktree()
	if err != nil {
		return "", fmt.Errorf("commit_files: worktree: %w", err)
	}
	if err := wt.AddGlob("."); err != nil {
		return "", fmt.Errorf("commit_files: add: %w", err)
	}
	hash, err := wt.Commit(message, &git.CommitOptions{
		Author: &object.Signature{
			Name:  c.id.AuthorName,
			Email: c.id.AuthorEmail,
			When:  time.Now(),
		},
	})
	if err != nil {
		return "", fmt.Errorf("commit_files: commit: %w", err)
	}
	return hash.String(), nil
}

func (c *realGitClient) Push(ctx context.Context, cloneDir, branch string) error {
	r, err := git.PlainOpen(cloneDir)
	if err != nil {
		return fmt.Errorf("push: open repo: %w", err)
	}
	basicAuth, err := c.basicAuth(ctx)
	if err != nil {
		return fmt.Errorf("push: %w", err)
	}
	refSpec := gitconfig.RefSpec(fmt.Sprintf("refs/heads/%s:refs/heads/%s", branch, branch))
	err = r.PushContext(ctx, &git.PushOptions{
		RemoteName: "origin",
		Auth:       basicAuth,
		RefSpecs:   []gitconfig.RefSpec{refSpec},
	})
	if err != nil && err != git.NoErrAlreadyUpToDate {
		return sanitiseAuthError(fmt.Errorf("push: %w", err), basicAuth.Password)
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
		var ghErr *gogithub.ErrorResponse
		if errors.As(err, &ghErr) && ghErr.Response != nil && ghErr.Response.StatusCode == 422 {
			existing, _, listErr := c.gh.PullRequests.List(ctx, c.owner, c.repo, &gogithub.PullRequestListOptions{
				State: "open",
				Head:  c.owner + ":" + head,
				Base:  base,
			})
			if listErr == nil && len(existing) > 0 {
				return existing[0].GetNumber(), nil
			}
		}
		return 0, fmt.Errorf("create_pr: %w", err)
	}
	return pr.GetNumber(), nil
}

const (
	graphQLPath             = "graphql"
	enableAutoMergeMutation = `mutation($pullRequestId: ID!) {
		enablePullRequestAutoMerge(input: {
			pullRequestId: $pullRequestId,
			mergeMethod: SQUASH
		}) { pullRequest { id } }
	}`
	disableAutoMergeMutation = `mutation($pullRequestId: ID!) {
		disablePullRequestAutoMerge(input: {
			pullRequestId: $pullRequestId
		}) { pullRequest { id } }
	}`
)

func (c *realGitClient) EnableAutoMerge(ctx context.Context, prNumber int) error {
	const op = "enable_auto_merge"
	pr, _, err := c.gh.PullRequests.Get(ctx, c.owner, c.repo, prNumber)
	if err != nil {
		return fmt.Errorf("%s: get pr: %w", op, err)
	}
	return c.pullRequestMutation(ctx, op, enableAutoMergeMutation, pr)
}

func (c *realGitClient) DisableAutoMerge(ctx context.Context, prNumber int) error {
	const op = "disable_auto_merge"
	pr, _, err := c.gh.PullRequests.Get(ctx, c.owner, c.repo, prNumber)
	if err != nil {
		return fmt.Errorf("%s: get pr: %w", op, err)
	}
	if pr.AutoMerge == nil {
		return nil
	}
	return c.pullRequestMutation(ctx, op, disableAutoMergeMutation, pr)
}

func (c *realGitClient) pullRequestMutation(ctx context.Context, op, mutation string, pr *gogithub.PullRequest) error {
	nodeID := pr.GetNodeID()
	if nodeID == "" {
		return fmt.Errorf("%s: PR #%d has no node_id", op, pr.GetNumber())
	}

	body, _ := json.Marshal(map[string]any{
		"query":     mutation,
		"variables": map[string]any{"pullRequestId": nodeID},
	})

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.gh.BaseURL.JoinPath(graphQLPath).String(), bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("%s: build request: %w", op, err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.gh.Client().Do(req)
	if err != nil {
		return fmt.Errorf("%s: post: %w", op, err)
	}
	defer func() { _ = resp.Body.Close() }()

	respBody, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("%s: status %d: %s", op, resp.StatusCode, strings.TrimSpace(string(respBody)))
	}

	var gqlResp struct {
		Errors []struct{ Message string } `json:"errors"`
	}
	if json.Unmarshal(respBody, &gqlResp) == nil && len(gqlResp.Errors) > 0 {
		return fmt.Errorf("%s: graphql: %s", op, gqlResp.Errors[0].Message)
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

const remediationGateCheckName = "remediation-gate"

const revertStepName = "git revert"

const revertAbortTimeout = 10 * time.Second

var gateFailedConclusions = map[string]bool{
	"failure":         true,
	"cancelled":       true,
	"timed_out":       true,
	"action_required": true,
}

func (c *realGitClient) GetCheckRunStatus(ctx context.Context, prNumber int) (bool, string, error) {
	pr, _, err := c.gh.PullRequests.Get(ctx, c.owner, c.repo, prNumber)
	if err != nil {
		return false, "", fmt.Errorf("get_check_run_status: get pr: %w", err)
	}
	headSHA := pr.GetHead().GetSHA()
	if headSHA == "" {
		return false, "", nil
	}
	runs, _, err := c.gh.Checks.ListCheckRunsForRef(ctx, c.owner, c.repo, headSHA, &gogithub.ListCheckRunsOptions{})
	if err != nil {
		return false, "", fmt.Errorf("get_check_run_status: list runs: %w", err)
	}
	for _, run := range runs.CheckRuns {
		if run.GetName() == remediationGateCheckName {
			conclusion := run.GetConclusion()
			return gateFailedConclusions[conclusion], conclusion, nil
		}
	}
	return false, "", nil
}

func (c *realGitClient) GetMergeableState(ctx context.Context, prNumber int) (string, error) {
	pr, _, err := c.gh.PullRequests.Get(ctx, c.owner, c.repo, prNumber)
	if err != nil {
		return "", fmt.Errorf("get_mergeable_state: get pr: %w", err)
	}
	return pr.GetMergeableState(), nil
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

func (c *realGitClient) ReadFile(ctx context.Context, cloneDir, branch, path string) (string, error) {
	r, err := git.PlainOpen(cloneDir)
	if err != nil {
		return "", fmt.Errorf("read_file: open repo: %w", err)
	}
	basicAuth, err := c.basicAuth(ctx)
	if err != nil {
		return "", fmt.Errorf("read_file: %w", err)
	}
	fetchErr := r.FetchContext(ctx, &git.FetchOptions{
		RefSpecs: []gitconfig.RefSpec{
			gitconfig.RefSpec("refs/heads/" + branch + ":refs/remotes/origin/" + branch),
		},
		Auth: basicAuth,
	})
	if fetchErr != nil && !errors.Is(fetchErr, git.NoErrAlreadyUpToDate) {
		return "", fmt.Errorf("branch not found: %s", branch)
	}
	ref, err := r.Reference(plumbing.NewRemoteReferenceName("origin", branch), true)
	if errors.Is(err, plumbing.ErrReferenceNotFound) {
		return "", fmt.Errorf("branch not found: %s", branch)
	}
	if err != nil {
		return "", fmt.Errorf("read_file: resolve ref: %w", err)
	}
	commit, err := r.CommitObject(ref.Hash())
	if err != nil {
		return "", fmt.Errorf("read_file: commit object: %w", err)
	}
	file, err := commit.File(path)
	if errors.Is(err, object.ErrFileNotFound) {
		return "", fmt.Errorf("path not found: %s", path)
	}
	if err != nil {
		return "", fmt.Errorf("read_file: file: %w", err)
	}
	contents, err := file.Contents()
	if err != nil {
		return "", fmt.Errorf("read_file: read contents: %w", err)
	}
	return contents, nil
}

func (c *realGitClient) ResolveManifestPath(_ context.Context, cloneDir, kustomizePath, kind, namespace, name string) (string, string, error) {
	return resolveManifestPath(cloneDir, kustomizePath, kind, namespace, name)
}

// go-git v5 does not expose a native Revert; fall back to the git binary.
func (c *realGitClient) RevertCommit(ctx context.Context, cloneDir, mergeCommitSHA, baseBranch, revertBranch string) (string, error) {
	token, err := c.id.Token(ctx)
	if err != nil {
		return "", fmt.Errorf("revert_commit: github token: %w", err)
	}
	env := c.gitEnv(token)
	steps := []struct {
		name string
		args []string
	}{
		{"fetch", []string{"fetch", "origin", baseBranch}},
		{"reset", []string{"reset", "--hard", "origin/" + baseBranch}},
		{"parent check", []string{"rev-parse", "--verify", "--quiet", mergeCommitSHA + "^"}},
		{revertStepName, []string{"revert", "--no-edit", mergeCommitSHA}},
		{"push", []string{"push", "origin", "HEAD:refs/heads/" + revertBranch}},
	}
	for _, step := range steps {
		cmd := exec.CommandContext(ctx, "git", append([]string{"-C", cloneDir}, step.args...)...)
		cmd.Env = env
		if out, err := cmd.CombinedOutput(); err != nil {
			if step.name == revertStepName {
				abortRevert(ctx, cloneDir, env)
			}
			return "", sanitiseAuthError(fmt.Errorf("revert_commit: %s: %w: %s", step.name, err, strings.TrimSpace(string(out))), token)
		}
	}

	r, err := git.PlainOpen(cloneDir)
	if err != nil {
		return "", fmt.Errorf("revert_commit: open repo: %w", err)
	}
	head, err := r.Head()
	if err != nil {
		return "", fmt.Errorf("revert_commit: read HEAD after revert: %w", err)
	}
	return head.Hash().String(), nil
}

// The abort runs detached from the request so a cancelled call never leaves the clone mid-revert.
func abortRevert(ctx context.Context, cloneDir string, env []string) {
	abortCtx, cancel := context.WithTimeout(context.WithoutCancel(ctx), revertAbortTimeout)
	defer cancel()
	abort := exec.CommandContext(abortCtx, "git", "-C", cloneDir, "revert", "--abort")
	abort.Env = env
	_ = abort.Run()
}

func (c *realGitClient) gitEnv(token string) []string {
	return append(os.Environ(),
		"GIT_CONFIG_COUNT=2",
		"GIT_CONFIG_KEY_0=http."+config.GitHubURLPrefix+".extraheader",
		"GIT_CONFIG_VALUE_0=AUTHORIZATION: basic "+basicCredentials(token),
		"GIT_CONFIG_KEY_1=credential.helper",
		"GIT_CONFIG_VALUE_1=",
		"GIT_AUTHOR_NAME="+c.id.AuthorName,
		"GIT_AUTHOR_EMAIL="+c.id.AuthorEmail,
		"GIT_COMMITTER_NAME="+c.id.AuthorName,
		"GIT_COMMITTER_EMAIL="+c.id.AuthorEmail,
	)
}
