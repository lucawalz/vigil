package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
)

const (
	MaxOutputBytesDefault = 4096
	GitHubURLPrefix       = "https://github.com/"
)

type Config struct {
	GitHubToken       string
	AppClientID       string
	AppPrivateKeyFile string
	RepoURL           string
	MaxOutputBytes    int
}

type AppEnv struct {
	ClientID       string
	PrivateKeyFile string
}

var (
	AgentAppEnv   = AppEnv{ClientID: "GITHUB_APP_CLIENT_ID", PrivateKeyFile: "GITHUB_APP_PRIVATE_KEY_FILE"}
	HarnessAppEnv = AppEnv{ClientID: "VIGIL_HARNESS_APP_CLIENT_ID", PrivateKeyFile: "VIGIL_HARNESS_APP_PRIVATE_KEY_FILE"}
)

func Load(app AppEnv) (*Config, error) {
	c := &Config{
		GitHubToken:       os.Getenv("GITHUB_TOKEN"),
		AppClientID:       os.Getenv(app.ClientID),
		AppPrivateKeyFile: os.Getenv(app.PrivateKeyFile),
		RepoURL:           os.Getenv("REPO_URL"),
		MaxOutputBytes:    envInt("MAX_OUTPUT_BYTES", MaxOutputBytesDefault),
	}
	switch {
	case c.AppClientID != "" && c.AppPrivateKeyFile == "":
		return nil, fmt.Errorf("%s is required when %s is set", app.PrivateKeyFile, app.ClientID)
	case c.AppClientID == "" && c.AppPrivateKeyFile != "":
		return nil, fmt.Errorf("%s is required when %s is set", app.ClientID, app.PrivateKeyFile)
	case !c.UsesApp() && c.GitHubToken == "":
		return nil, fmt.Errorf("GITHUB_TOKEN or %s with %s is required", app.ClientID, app.PrivateKeyFile)
	}
	return c, nil
}

func (c *Config) UsesApp() bool {
	return c.AppClientID != ""
}

func (c *Config) Repository() (owner, repo string, err error) {
	path := strings.TrimSuffix(strings.TrimPrefix(c.RepoURL, GitHubURLPrefix), ".git")
	parts := strings.SplitN(path, "/", 2)
	if !strings.HasPrefix(c.RepoURL, GitHubURLPrefix) || len(parts) != 2 || parts[0] == "" || parts[1] == "" {
		return "", "", fmt.Errorf("cannot parse REPO_URL %q - expected %sowner/repo.git", c.RepoURL, GitHubURLPrefix)
	}
	return parts[0], parts[1], nil
}

func envInt(key string, fallback int) int {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			return n
		}
	}
	return fallback
}
