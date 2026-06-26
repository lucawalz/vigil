package main

import (
	"fmt"
	"log"
	"os"

	"github.com/mark3labs/mcp-go/server"

	"github.com/lucawalz/vigil/mcp-servers/nixos-mcp/internal/config"
	"github.com/lucawalz/vigil/mcp-servers/nixos-mcp/internal/nixos"
	mcpserver "github.com/lucawalz/vigil/mcp-servers/nixos-mcp/internal/server"
)

func main() {
	log.SetOutput(os.Stderr)

	cfg := config.Load()
	if len(cfg.SSHHosts) == 0 {
		log.Fatal("nixos-mcp: SSH_HOSTS is required; refusing to start without an allow-list")
	}

	client, err := nixos.NewRealNixOSClient(cfg.SSHUser, cfg.SSHKeyPath, cfg.SSHHosts, cfg.SSHDialTimeout, cfg.SSHDialRetries, cfg.SSHDialBackoff)
	if err != nil {
		fmt.Fprintf(os.Stderr, "nixos client: %v\n", err)
		os.Exit(1)
	}

	s := mcpserver.NewServer(client, cfg)

	if err := server.ServeStdio(s); err != nil {
		fmt.Fprintf(os.Stderr, "server error: %v\n", err)
		os.Exit(1)
	}
}
