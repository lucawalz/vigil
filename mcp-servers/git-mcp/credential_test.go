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
