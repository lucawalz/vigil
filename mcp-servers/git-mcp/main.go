package main

import (
	"fmt"
	"log"
	"os"

	"github.com/mark3labs/mcp-go/server"

	"github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/config"
	"github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/git"
	mcpserver "github.com/lucawalz/vigil/mcp-servers/git-mcp/internal/server"
)

func main() {
	log.SetOutput(os.Stderr)

	cfg := config.Load()
	if cfg.GitHubToken == "" {
		log.Fatal("git-mcp: GITHUB_TOKEN is required")
	}
	if cfg.RepoURL == "" {
		log.Fatal("git-mcp: REPO_URL is required")
	}
	client := git.NewRealGitClient(cfg)
	s := mcpserver.NewServer(client, cfg)

	if err := server.ServeStdio(s); err != nil {
		fmt.Fprintf(os.Stderr, "server error: %v\n", err)
		os.Exit(1)
	}
}
