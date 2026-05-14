package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
)

const MaxOutputBytesDefault = 4096

type Config struct {
	GitHubToken    string
	RepoURL        string
	MaxOutputBytes int
}

func Load() *Config {
	return &Config{
		GitHubToken:    os.Getenv("GITHUB_TOKEN"),
		RepoURL:        os.Getenv("REPO_URL"),
		MaxOutputBytes: envInt("MAX_OUTPUT_BYTES", MaxOutputBytesDefault),
	}
}

func (c *Config) AuthURL() string {
	return strings.Replace(c.RepoURL, "https://", fmt.Sprintf("https://x-access-token:%s@", c.GitHubToken), 1)
}

func envInt(key string, fallback int) int {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			return n
		}
	}
	return fallback
}
