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

	client, err := nixos.NewRealNixOSClient(cfg.SSHUser, cfg.SSHKeyPath, cfg.SSHHosts)
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
