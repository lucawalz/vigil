package main

import (
	"bufio"
	"context"
	"fmt"
	"io"

	"github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/auth"
)

const (
	credentialCommand   = "credential"
	credentialGetAction = "get"
	credentialUsername  = "x-access-token"
)

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
