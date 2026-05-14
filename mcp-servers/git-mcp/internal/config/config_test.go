package config

import (
	"strings"
	"testing"
)

func TestLoad_defaults(t *testing.T) {
	t.Setenv("GITHUB_TOKEN", "")
	t.Setenv("REPO_URL", "")
	t.Setenv("MAX_OUTPUT_BYTES", "")

	cfg := Load()
	if cfg.GitHubToken != "" {
		t.Errorf("expected empty GitHubToken, got %q", cfg.GitHubToken)
	}
	if cfg.RepoURL != "" {
		t.Errorf("expected empty RepoURL, got %q", cfg.RepoURL)
	}
	if cfg.MaxOutputBytes != MaxOutputBytesDefault {
		t.Errorf("expected default MaxOutputBytes %d, got %d", MaxOutputBytesDefault, cfg.MaxOutputBytes)
	}
}

func TestLoad_envVars(t *testing.T) {
	t.Setenv("GITHUB_TOKEN", "tok123")
	t.Setenv("REPO_URL", "https://github.com/owner/repo.git")
	t.Setenv("MAX_OUTPUT_BYTES", "1024")

	cfg := Load()
	if cfg.GitHubToken != "tok123" {
		t.Errorf("expected GitHubToken %q, got %q", "tok123", cfg.GitHubToken)
	}
	if cfg.RepoURL != "https://github.com/owner/repo.git" {
		t.Errorf("expected RepoURL %q, got %q", "https://github.com/owner/repo.git", cfg.RepoURL)
	}
	if cfg.MaxOutputBytes != 1024 {
		t.Errorf("expected MaxOutputBytes 1024, got %d", cfg.MaxOutputBytes)
	}
}

func TestAuthURL_injectsToken(t *testing.T) {
	cfg := &Config{
		GitHubToken: "mytoken",
		RepoURL:     "https://github.com/lucawalz/vigil.git",
	}
	got := cfg.AuthURL()
	want := "https://x-access-token:mytoken@github.com/lucawalz/vigil.git"
	if got != want {
		t.Errorf("AuthURL() = %q, want %q", got, want)
	}
}

func TestAuthURL_xAccessTokenPrefix(t *testing.T) {
	cfg := &Config{
		GitHubToken: "secret",
		RepoURL:     "https://github.com/org/repo.git",
	}
	got := cfg.AuthURL()
	if !strings.Contains(got, "x-access-token:secret@") {
		t.Errorf("AuthURL() %q does not contain expected token injection", got)
	}
}
