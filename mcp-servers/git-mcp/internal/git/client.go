package git

import (
	"context"
	"fmt"
	"net/http"

	"github.com/google/go-github/v86/github"
	"golang.org/x/oauth2"

	"github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/config"
)

type GitClient interface {
	Clone(ctx context.Context, authURL string) (cloneDir string, err error)
	CreateBranch(ctx context.Context, cloneDir, branch string) error
	WriteFile(ctx context.Context, cloneDir, manifestPath, content string) error
	CommitFiles(ctx context.Context, cloneDir, branch, message string) (sha string, err error)
	Push(ctx context.Context, cloneDir, branch string) error
	CreatePR(ctx context.Context, title, head, base, body string) (prNumber int, err error)
	GetPRStatus(ctx context.Context, prNumber int) (state string, merged bool, mergeCommitSHA string, err error)
	RevertCommit(ctx context.Context, cloneDir, mergeCommitSHA string) (revertSHA string, err error)
}

type realGitClient struct {
	gh      *github.Client
	authURL string
}

func NewRealGitClient(cfg *config.Config) GitClient {
	var httpClient *http.Client
	if cfg.GitHubToken != "" {
		ts := oauth2.StaticTokenSource(&oauth2.Token{AccessToken: cfg.GitHubToken})
		httpClient = oauth2.NewClient(context.Background(), ts)
	}
	return &realGitClient{
		gh:      github.NewClient(httpClient),
		authURL: cfg.AuthURL(),
	}
}

func (c *realGitClient) Clone(_ context.Context, _ string) (string, error) {
	return "", fmt.Errorf("not implemented: Clone")
}

func (c *realGitClient) CreateBranch(_ context.Context, _, _ string) error {
	return fmt.Errorf("not implemented: CreateBranch")
}

func (c *realGitClient) WriteFile(_ context.Context, _, _, _ string) error {
	return fmt.Errorf("not implemented: WriteFile")
}

func (c *realGitClient) CommitFiles(_ context.Context, _, _, _ string) (string, error) {
	return "", fmt.Errorf("not implemented: CommitFiles")
}

func (c *realGitClient) Push(_ context.Context, _, _ string) error {
	return fmt.Errorf("not implemented: Push")
}

func (c *realGitClient) CreatePR(_ context.Context, _, _, _, _ string) (int, error) {
	return 0, fmt.Errorf("not implemented: CreatePR")
}

func (c *realGitClient) GetPRStatus(_ context.Context, _ int) (string, bool, string, error) {
	return "", false, "", fmt.Errorf("not implemented: GetPRStatus")
}

func (c *realGitClient) RevertCommit(_ context.Context, _, _ string) (string, error) {
	return "", fmt.Errorf("not implemented: RevertCommit")
}
