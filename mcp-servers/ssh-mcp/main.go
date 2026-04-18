package main

import (
	"fmt"
	"log"
	"os"

	"github.com/mark3labs/mcp-go/server"

	"github.com/lucawalz/vigil/mcp-servers/ssh-mcp/internal/config"
	"github.com/lucawalz/vigil/mcp-servers/ssh-mcp/internal/ssh"
	mcpserver "github.com/lucawalz/vigil/mcp-servers/ssh-mcp/internal/server"
)

func main() {
	log.SetOutput(os.Stderr)

	cfg := config.Load()

	client, err := ssh.NewRealSSHClient(cfg.SSHUser, cfg.SSHKeyPath, cfg.SSHHosts)
	if err != nil {
		fmt.Fprintf(os.Stderr, "ssh client: %v\n", err)
		os.Exit(1)
	}

	s := mcpserver.NewServer(client, cfg)

	if err := server.ServeStdio(s); err != nil {
		fmt.Fprintf(os.Stderr, "server error: %v\n", err)
		os.Exit(1)
	}
}
