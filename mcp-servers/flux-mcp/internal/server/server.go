package server

import (
	"context"
	"sync"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"

	"github.com/lucawalz/vigil/mcp-servers/flux-mcp/internal/config"
	"github.com/lucawalz/vigil/mcp-servers/flux-mcp/internal/flux"
)

// FluxServer holds per-resource suspend state. guardMutation checks that the
// specific named resource was suspended by this session before allowing mutations.
type FluxServer struct {
	suspendedNames map[string]bool
	mu             sync.Mutex
}

func NewFluxServer(client flux.FluxClient, cfg *config.Config) *server.MCPServer {
	s := &FluxServer{
		suspendedNames: make(map[string]bool),
	}

	mcpServer := server.NewMCPServer("flux-mcp", "1.0.0",
		server.WithToolCapabilities(true),
	)

	maxBytes := cfg.MaxOutputBytesDescribe

	// suspend_kustomization: NOT guarded — this is the guard enabler.
	mcpServer.AddTool(
		mcp.NewTool("suspend_kustomization",
			mcp.WithDescription("Suspend a Flux Kustomization to allow safe mutations"),
			mcp.WithString("namespace", mcp.Required(), mcp.Description("Kubernetes namespace")),
			mcp.WithString("name", mcp.Required(), mcp.Description("Kustomization name")),
		),
		flux.HandleSuspendKustomization(client, s.onSuspend),
	)

	mcpServer.AddTool(
		mcp.NewTool("resume_kustomization",
			mcp.WithDescription("Resume a previously suspended Flux Kustomization"),
			mcp.WithString("namespace", mcp.Required(), mcp.Description("Kubernetes namespace")),
			mcp.WithString("name", mcp.Required(), mcp.Description("Kustomization name")),
		),
		s.guardMutation(flux.HandleResumeKustomization(client, s.onResume)),
	)

	mcpServer.AddTool(
		mcp.NewTool("reconcile_kustomization",
			mcp.WithDescription("Trigger reconciliation of a Flux Kustomization"),
			mcp.WithString("namespace", mcp.Required(), mcp.Description("Kubernetes namespace")),
			mcp.WithString("name", mcp.Required(), mcp.Description("Kustomization name")),
		),
		s.guardMutation(flux.HandleReconcileKustomization(client, maxBytes)),
	)

	mcpServer.AddTool(
		mcp.NewTool("get_kustomization_status",
			mcp.WithDescription("Get status of a Flux Kustomization"),
			mcp.WithString("namespace", mcp.Required(), mcp.Description("Kubernetes namespace")),
			mcp.WithString("name", mcp.Required(), mcp.Description("Kustomization name")),
		),
		flux.HandleGetKustomizationStatus(client, maxBytes),
	)

	return mcpServer
}

func (s *FluxServer) guardMutation(next server.ToolHandlerFunc) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		name, _ := req.GetArguments()["name"].(string)
		s.mu.Lock()
		allowed := name != "" && s.suspendedNames[name]
		s.mu.Unlock()
		if !allowed {
			return mcp.NewToolResultError(
				"flux_suspended guard: call suspend_kustomization for this resource before any mutating tool",
			), nil
		}
		return next(ctx, req)
	}
}

func (s *FluxServer) onSuspend(name string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.suspendedNames[name] = true
}

// onResume removes the name from the suspended set.
func (s *FluxServer) onResume(name string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	delete(s.suspendedNames, name)
	return true
}
