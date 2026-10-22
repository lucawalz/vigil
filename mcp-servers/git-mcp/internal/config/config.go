package config

import (
	"errors"
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

func Load() (*Config, error) {
	c := &Config{
		GitHubToken:       os.Getenv("GITHUB_TOKEN"),
		AppClientID:       os.Getenv("GITHUB_APP_CLIENT_ID"),
		AppPrivateKeyFile: os.Getenv("GITHUB_APP_PRIVATE_KEY_FILE"),
		RepoURL:           os.Getenv("REPO_URL"),
		MaxOutputBytes:    envInt("MAX_OUTPUT_BYTES", MaxOutputBytesDefault),
	}
	switch {
	case c.AppClientID != "" && c.AppPrivateKeyFile == "":
		return nil, errors.New("GITHUB_APP_PRIVATE_KEY_FILE is required when GITHUB_APP_CLIENT_ID is set")
	case c.AppClientID == "" && c.AppPrivateKeyFile != "":
		return nil, errors.New("GITHUB_APP_CLIENT_ID is required when GITHUB_APP_PRIVATE_KEY_FILE is set")
	case !c.UsesApp() && c.GitHubToken == "":
		return nil, errors.New("GITHUB_TOKEN or GITHUB_APP_CLIENT_ID with GITHUB_APP_PRIVATE_KEY_FILE is required")
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
