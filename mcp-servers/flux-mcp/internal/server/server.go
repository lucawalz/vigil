package server

import (
	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"

	"github.com/lucawalz/vigil/mcp-servers/flux-mcp/internal/config"
	"github.com/lucawalz/vigil/mcp-servers/flux-mcp/internal/flux"
)

type TextResult struct {
	Text string `json:"text" jsonschema:"Output text"`
}

func NewFluxServer(client flux.FluxClient, cfg *config.Config) *server.MCPServer {
	mcpServer := server.NewMCPServer("flux-mcp", "1.0.0",
		server.WithToolCapabilities(true),
	)

	maxBytes := cfg.MaxOutputBytesDescribe

	mcpServer.AddTool(
		mcp.NewTool("reconcile_kustomization",
			mcp.WithDescription("Trigger reconciliation of a Flux Kustomization"),
			mcp.WithString("namespace", mcp.Required(), mcp.Description("Kubernetes namespace")),
			mcp.WithString("name", mcp.Required(), mcp.Description("Kustomization name")),
			mcp.WithOutputSchema[TextResult](),
		),
		flux.HandleReconcileKustomization(client, maxBytes),
	)

	mcpServer.AddTool(
		mcp.NewTool("get_kustomization_status",
			mcp.WithDescription("Get status of a Flux Kustomization"),
			mcp.WithString("namespace", mcp.Required(), mcp.Description("Kubernetes namespace")),
			mcp.WithString("name", mcp.Required(), mcp.Description("Kustomization name")),
			mcp.WithOutputSchema[TextResult](),
		),
		flux.HandleGetKustomizationStatus(client, maxBytes),
	)

	mcpServer.AddTool(
		mcp.NewTool("get_gitrepository_status",
			mcp.WithDescription("Get status of a Flux GitRepository source"),
			mcp.WithString("namespace", mcp.Required(), mcp.Description("Kubernetes namespace")),
			mcp.WithString("name", mcp.Required(), mcp.Description("GitRepository name")),
			mcp.WithOutputSchema[TextResult](),
		),
		flux.HandleGetGitRepositoryStatus(client, maxBytes),
	)

	return mcpServer
}
