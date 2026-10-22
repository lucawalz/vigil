package main

import (
	"bufio"
	"context"
	"fmt"
	"io"

	"github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/auth"
	"github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/config"
)

const (
	credentialCommand        = "credential"
	harnessCredentialCommand = "harness-credential"
	credentialGetAction      = "get"
	credentialUsername       = "x-access-token"
)

var credentialAppEnvs = map[string]config.AppEnv{
	credentialCommand:        config.AgentAppEnv,
	harnessCredentialCommand: config.HarnessAppEnv,
}

func tokenFromEnv(app config.AppEnv) func(context.Context) (auth.TokenFunc, error) {
	return func(ctx context.Context) (auth.TokenFunc, error) {
		cfg, err := config.Load(app)
		if err != nil {
			return nil, err
		}
		return auth.NewTokenFunc(ctx, cfg)
	}
}

func credential(ctx context.Context, action string, in io.Reader, out io.Writer, newToken func(context.Context) (auth.TokenFunc, error)) error {
	if action != credentialGetAction {
		return nil
	}
	scanner := bufio.NewScanner(in)
	for scanner.Scan() && scanner.Text() != "" {
	}
	if err := scanner.Err(); err != nil {
		return fmt.Errorf("read credential request: %w", err)
	}
	tokenFunc, err := newToken(ctx)
	if err != nil {
		return err
	}
	token, err := tokenFunc(ctx)
	if err != nil {
		return err
	}
	_, err = fmt.Fprintf(out, "username=%s\npassword=%s\n", credentialUsername, token)
	return err
}
