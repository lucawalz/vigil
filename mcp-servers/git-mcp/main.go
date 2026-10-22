package main

import (
	"context"
	"fmt"
	"log"
	"os"

	"github.com/mark3labs/mcp-go/server"

	"github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/auth"
	"github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/config"
	"github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/git"
	mcpserver "github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/server"
)

func main() {
	log.SetOutput(os.Stderr)
	ctx := context.Background()

	if len(os.Args) > 1 && os.Args[1] == credentialCommand {
		action := ""
		if len(os.Args) > 2 {
			action = os.Args[2]
		}
		newToken := func(ctx context.Context) (auth.TokenFunc, error) {
			cfg, err := config.Load()
			if err != nil {
				return nil, err
			}
			return auth.NewTokenFunc(ctx, cfg)
		}
		if err := credential(ctx, action, os.Stdin, os.Stdout, newToken); err != nil {
			log.Fatalf("git-mcp credential: %v", err)
		}
		return
	}

	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("git-mcp: %v", err)
	}
	if cfg.RepoURL == "" {
		log.Fatal("git-mcp: REPO_URL is required")
	}
	id, err := auth.NewIdentity(ctx, cfg)
	if err != nil {
		log.Fatalf("git-mcp: %v", err)
	}
	client := git.NewRealGitClient(cfg, id)
	s := mcpserver.NewServer(client, cfg)

	if err := server.ServeStdio(s); err != nil {
		fmt.Fprintf(os.Stderr, "server error: %v\n", err)
		os.Exit(1)
	}
}
