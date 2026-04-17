package main

import (
	"fmt"
	"log"
	"os"

	"github.com/mark3labs/mcp-go/server"

	"github.com/lucawalz/vigil/mcp-servers/flux-mcp/internal/config"
	"github.com/lucawalz/vigil/mcp-servers/flux-mcp/internal/flux"
	mcpserver "github.com/lucawalz/vigil/mcp-servers/flux-mcp/internal/server"
)

func main() {
	log.SetOutput(os.Stderr)

	cfg := config.Load()

	restCfg, err := config.BuildRestConfig()
	if err != nil {
		fmt.Fprintf(os.Stderr, "kubeconfig: %v\n", err)
		os.Exit(1)
	}

	client := flux.NewRealFluxClient(restCfg)
	s := mcpserver.NewFluxServer(client, cfg)

	if err := server.ServeStdio(s); err != nil {
		fmt.Fprintf(os.Stderr, "server error: %v\n", err)
		os.Exit(1)
	}
}
