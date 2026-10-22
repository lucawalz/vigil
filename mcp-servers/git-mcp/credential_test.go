package main

import (
	"bytes"
	"context"
	"strings"
	"testing"

	"github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/auth"
)

func TestCredential_getPrintsToken(t *testing.T) {
	var out bytes.Buffer
	in := strings.NewReader("protocol=https\nhost=github.com\n\n")
	newToken := func(context.Context) (auth.TokenFunc, error) { return auth.Static("tok-1"), nil }

	if err := credential(context.Background(), "get", in, &out, newToken); err != nil {
		t.Fatalf("credential get: %v", err)
	}
	if want := "username=x-access-token\npassword=tok-1\n"; out.String() != want {
		t.Errorf("output = %q, want %q", out.String(), want)
	}
}

func setHarnessEnv(t *testing.T, token, clientID, keyFile string) {
	t.Helper()
	t.Setenv("GITHUB_TOKEN", token)
	t.Setenv("GITHUB_APP_CLIENT_ID", "Iv23agent")
	t.Setenv("GITHUB_APP_PRIVATE_KEY_FILE", "/nonexistent/agent.pem")
	t.Setenv("VIGIL_HARNESS_APP_CLIENT_ID", clientID)
	t.Setenv("VIGIL_HARNESS_APP_PRIVATE_KEY_FILE", keyFile)
}

func harnessCredential(action string, out *bytes.Buffer) error {
	return credential(context.Background(), action, strings.NewReader("host=github.com\n\n"), out, tokenFromEnv(credentialAppEnvs[harnessCredentialCommand]))
}

func TestHarnessCredential_ignoresAgentAppAndFallsBackToToken(t *testing.T) {
	setHarnessEnv(t, "harness-tok", "", "")
	var out bytes.Buffer
	if err := harnessCredential(credentialGetAction, &out); err != nil {
		t.Fatalf("harness-credential get: %v", err)
	}
	if want := "username=x-access-token\npassword=harness-tok\n"; out.String() != want {
		t.Errorf("output = %q, want %q", out.String(), want)
	}
}

func TestHarnessCredential_halfPairFails(t *testing.T) {
	setHarnessEnv(t, "harness-tok", "Iv23harness", "")
	var out bytes.Buffer
	err := harnessCredential(credentialGetAction, &out)
	if err == nil || !strings.Contains(err.Error(), "VIGIL_HARNESS_APP_PRIVATE_KEY_FILE") {
		t.Errorf("expected error naming VIGIL_HARNESS_APP_PRIVATE_KEY_FILE, got %v", err)
	}
	if out.Len() != 0 {
		t.Errorf("printed %q on failure, want nothing", out.String())
	}
}

func TestHarnessCredential_otherActionsPrintNothing(t *testing.T) {
	setHarnessEnv(t, "", "Iv23harness", "")
	for _, action := range []string{"store", "erase"} {
		var out bytes.Buffer
		if err := harnessCredential(action, &out); err != nil {
			t.Fatalf("harness-credential %s: %v", action, err)
		}
		if out.Len() != 0 {
			t.Errorf("%s printed %q, want nothing", action, out.String())
		}
	}
}

func TestCredential_otherActionsPrintNothing(t *testing.T) {
	for _, action := range []string{"store", "erase"} {
		var out bytes.Buffer
		newToken := func(context.Context) (auth.TokenFunc, error) {
			t.Fatalf("%s must not load a token", action)
			return nil, nil
		}
		if err := credential(context.Background(), action, strings.NewReader("host=github.com\n\n"), &out, newToken); err != nil {
			t.Fatalf("credential %s: %v", action, err)
		}
		if out.Len() != 0 {
			t.Errorf("%s printed %q, want nothing", action, out.String())
		}
	}
}
