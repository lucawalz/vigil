package config

import (
	"strconv"
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

	cfg, err := Load(AgentAppEnv)
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

	cfg, err := Load(AgentAppEnv)
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if cfg.MaxOutputBytes != MaxOutputBytesDefault {
		t.Errorf("MaxOutputBytes = %d, want %d", cfg.MaxOutputBytes, MaxOutputBytesDefault)
	}
}

func TestLoad_app(t *testing.T) {
	setAuthEnv(t, "", "Iv23abc", "/run/key.pem")

	cfg, err := Load(AgentAppEnv)
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if !cfg.UsesApp() || cfg.AppClientID != "Iv23abc" || cfg.AppPrivateKeyFile != "/run/key.pem" {
		t.Errorf("expected app mode, got %+v", cfg)
	}
}

func TestLoad_harnessAppReadsHarnessNames(t *testing.T) {
	setAuthEnv(t, "", "Iv23agent", "/run/agent.pem")
	t.Setenv("VIGIL_HARNESS_APP_CLIENT_ID", "Iv23harness")
	t.Setenv("VIGIL_HARNESS_APP_PRIVATE_KEY_FILE", "/run/harness.pem")

	cfg, err := Load(HarnessAppEnv)
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if cfg.AppClientID != "Iv23harness" || cfg.AppPrivateKeyFile != "/run/harness.pem" {
		t.Errorf("expected harness app settings, got %+v", cfg)
	}
}

func TestLoad_incompleteAppFails(t *testing.T) {
	for _, app := range []AppEnv{AgentAppEnv, HarnessAppEnv} {
		cases := map[string]struct{ clientID, keyFile, missing string }{
			"client id only": {"Iv23abc", "", app.PrivateKeyFile},
			"key file only":  {"", "/run/key.pem", app.ClientID},
		}
		for name, tc := range cases {
			t.Run(app.ClientID+" "+name, func(t *testing.T) {
				t.Setenv("GITHUB_TOKEN", "tok")
				t.Setenv(app.ClientID, tc.clientID)
				t.Setenv(app.PrivateKeyFile, tc.keyFile)
				_, err := Load(app)
				if err == nil || !strings.Contains(err.Error(), tc.missing) {
					t.Errorf("expected error naming %s, got %v", tc.missing, err)
				}
			})
		}
	}
}

func TestLoad_noCredentialsFails(t *testing.T) {
	setAuthEnv(t, "", "", "")
	_, err := Load(AgentAppEnv)
	if err == nil || !strings.Contains(err.Error(), "GITHUB_TOKEN") {
		t.Errorf("expected error naming GITHUB_TOKEN, got %v", err)
	}
}

func TestGateWaitTimeoutSeconds_unsetUsesDefault(t *testing.T) {
	t.Setenv(GateWaitTimeoutEnv, "")
	got, err := GateWaitTimeoutSeconds()
	if err != nil || got != DefaultWaitForGateTimeoutSeconds {
		t.Errorf("GateWaitTimeoutSeconds() = %d, %v; want %d, nil", got, err, DefaultWaitForGateTimeoutSeconds)
	}
}

func TestGateWaitTimeoutSeconds_readsValue(t *testing.T) {
	t.Setenv(GateWaitTimeoutEnv, "120")
	got, err := GateWaitTimeoutSeconds()
	if err != nil || got != 120 {
		t.Errorf("GateWaitTimeoutSeconds() = %d, %v; want 120, nil", got, err)
	}
}

func TestGateWaitTimeoutSeconds_invalidFails(t *testing.T) {
	aboveBound := strconv.Itoa(MaxWaitForGateTimeoutSeconds + 1)
	for _, value := range []string{"0", "-5", "eight", aboveBound} {
		t.Run(value, func(t *testing.T) {
			t.Setenv(GateWaitTimeoutEnv, value)
			_, err := GateWaitTimeoutSeconds()
			if err == nil || !strings.Contains(err.Error(), GateWaitTimeoutEnv) || !strings.Contains(err.Error(), strconv.Itoa(MaxWaitForGateTimeoutSeconds)) {
				t.Errorf("expected error naming %s and the bound, got %v", GateWaitTimeoutEnv, err)
			}
		})
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
