package main

import (
	"fmt"
	"log"
	"os"

	"github.com/mark3labs/mcp-go/server"

	"github.com/lucawalz/vigil/mcp-servers/kubectl-mcp/internal/config"
	"github.com/lucawalz/vigil/mcp-servers/kubectl-mcp/internal/k8s"
	mcpserver "github.com/lucawalz/vigil/mcp-servers/kubectl-mcp/internal/server"
)

func main() {
	log.SetOutput(os.Stderr)

	cfg := config.Load()

	restCfg, err := config.BuildRestConfig()
	if err != nil {
		fmt.Fprintf(os.Stderr, "kubeconfig: %v\n", err)
		os.Exit(1)
	}

	client := k8s.NewRealK8sClient(restCfg)
	s := mcpserver.NewServer(client, cfg)

	if err := server.ServeStdio(s); err != nil {
		fmt.Fprintf(os.Stderr, "server error: %v\n", err)
		os.Exit(1)
	}
}
