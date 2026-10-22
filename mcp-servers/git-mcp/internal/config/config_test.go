package config

import (
	"strings"
	"testing"
)

func setAuthEnv(t *testing.T, token, clientID, keyFile string) {
	t.Helper()
	t.Setenv("GITHUB_TOKEN", token)
	t.Setenv("GITHUB_APP_CLIENT_ID", clientID)
	t.Setenv("GITHUB_APP_PRIVATE_KEY_FILE", keyFile)
}

func TestLoad_staticToken(t *testing.T) {
	setAuthEnv(t, "tok123", "", "")
	t.Setenv("REPO_URL", "https://github.com/owner/repo.git")
	t.Setenv("MAX_OUTPUT_BYTES", "1024")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if cfg.GitHubToken != "tok123" || cfg.UsesApp() {
		t.Errorf("expected static token mode, got %+v", cfg)
	}
	if cfg.RepoURL != "https://github.com/owner/repo.git" {
		t.Errorf("RepoURL = %q", cfg.RepoURL)
	}
	if cfg.MaxOutputBytes != 1024 {
		t.Errorf("MaxOutputBytes = %d, want 1024", cfg.MaxOutputBytes)
	}
}

func TestLoad_defaultMaxOutputBytes(t *testing.T) {
	setAuthEnv(t, "tok", "", "")
	t.Setenv("MAX_OUTPUT_BYTES", "")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if cfg.MaxOutputBytes != MaxOutputBytesDefault {
		t.Errorf("MaxOutputBytes = %d, want %d", cfg.MaxOutputBytes, MaxOutputBytesDefault)
	}
}

func TestLoad_app(t *testing.T) {
	setAuthEnv(t, "", "Iv23abc", "/run/key.pem")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if !cfg.UsesApp() || cfg.AppClientID != "Iv23abc" || cfg.AppPrivateKeyFile != "/run/key.pem" {
		t.Errorf("expected app mode, got %+v", cfg)
	}
}

func TestLoad_incompleteAppFails(t *testing.T) {
	cases := map[string]struct{ clientID, keyFile, missing string }{
		"client id only": {"Iv23abc", "", "GITHUB_APP_PRIVATE_KEY_FILE"},
		"key file only":  {"", "/run/key.pem", "GITHUB_APP_CLIENT_ID"},
	}
	for name, tc := range cases {
		t.Run(name, func(t *testing.T) {
			setAuthEnv(t, "tok", tc.clientID, tc.keyFile)
			_, err := Load()
			if err == nil || !strings.Contains(err.Error(), tc.missing) {
				t.Errorf("expected error naming %s, got %v", tc.missing, err)
			}
		})
	}
}

func TestLoad_noCredentialsFails(t *testing.T) {
	setAuthEnv(t, "", "", "")
	_, err := Load()
	if err == nil || !strings.Contains(err.Error(), "GITHUB_TOKEN") {
		t.Errorf("expected error naming GITHUB_TOKEN, got %v", err)
	}
}

func TestRepository(t *testing.T) {
	owner, repo, err := (&Config{RepoURL: "https://github.com/lucawalz/vigil.git"}).Repository()
	if err != nil || owner != "lucawalz" || repo != "vigil" {
		t.Errorf("Repository() = %q, %q, %v", owner, repo, err)
	}
	if _, _, err := (&Config{RepoURL: "git@github.com:x/y.git"}).Repository(); err == nil {
		t.Error("expected error for non-https URL")
	}
}
