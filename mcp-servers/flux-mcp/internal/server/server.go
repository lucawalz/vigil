package server

import (
	"context"
	"sync"
	"sync/atomic"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"

	"github.com/lucawalz/vigil/mcp-servers/flux-mcp/internal/config"
	"github.com/lucawalz/vigil/mcp-servers/flux-mcp/internal/flux"
)

// FluxServer holds the session-scoped flux_suspended guard. The guard enforces
// that suspend_kustomization is called before any mutating tool in this session,
// making it impossible for the agent to bypass the invariant.
type FluxServer struct {
	mcpServer      *server.MCPServer
	client         flux.FluxClient
	suspended      atomic.Bool
	suspendedNames map[string]bool
	mu             sync.Mutex
	maxOutputBytes int
}

func NewFluxServer(client flux.FluxClient, cfg *config.Config) *server.MCPServer {
	s := &FluxServer{
		client:         client,
		suspendedNames: make(map[string]bool),
		maxOutputBytes: cfg.MaxOutputBytesDescribe,
	}

	s.mcpServer = server.NewMCPServer("flux-mcp", "1.0.0",
		server.WithToolCapabilities(true),
	)

	maxBytes := cfg.MaxOutputBytesDescribe

	// suspend_kustomization: NOT guarded — this is the guard enabler.
	s.mcpServer.AddTool(
		mcp.NewTool("suspend_kustomization",
			mcp.WithDescription("Suspend a Flux Kustomization to allow safe mutations"),
			mcp.WithString("namespace", mcp.Required(), mcp.Description("Kubernetes namespace")),
			mcp.WithString("name", mcp.Required(), mcp.Description("Kustomization name")),
		),
		flux.HandleSuspendKustomization(client, maxBytes, s.onSuspend),
	)

	s.mcpServer.AddTool(
		mcp.NewTool("resume_kustomization",
			mcp.WithDescription("Resume a previously suspended Flux Kustomization"),
			mcp.WithString("namespace", mcp.Required(), mcp.Description("Kubernetes namespace")),
			mcp.WithString("name", mcp.Required(), mcp.Description("Kustomization name")),
		),
		s.guardMutation(flux.HandleResumeKustomization(client, maxBytes, s.onResume)),
	)

	s.mcpServer.AddTool(
		mcp.NewTool("reconcile_kustomization",
			mcp.WithDescription("Trigger reconciliation of a Flux Kustomization"),
			mcp.WithString("namespace", mcp.Required(), mcp.Description("Kubernetes namespace")),
			mcp.WithString("name", mcp.Required(), mcp.Description("Kustomization name")),
		),
		s.guardMutation(flux.HandleReconcileKustomization(client, maxBytes)),
	)

	s.mcpServer.AddTool(
		mcp.NewTool("get_kustomization_status",
			mcp.WithDescription("Get status of a Flux Kustomization"),
			mcp.WithString("namespace", mcp.Required(), mcp.Description("Kubernetes namespace")),
			mcp.WithString("name", mcp.Required(), mcp.Description("Kustomization name")),
		),
		flux.HandleGetKustomizationStatus(client, maxBytes),
	)

	return s.mcpServer
}

func (s *FluxServer) guardMutation(next server.ToolHandlerFunc) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		if !s.suspended.Load() {
			return mcp.NewToolResultError(
				"flux_suspended guard: call suspend_kustomization before any mutating tool",
			), nil
		}
		return next(ctx, req)
	}
}

func (s *FluxServer) onSuspend(name string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.suspendedNames[name] = true
	s.suspended.Store(true)
}

// onResume removes the name and only resets the flag when all suspended names
// have been resumed — prevents premature guard reset on partial resume.
func (s *FluxServer) onResume(name string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	delete(s.suspendedNames, name)
	if len(s.suspendedNames) == 0 {
		s.suspended.Store(false)
	}
	return true
}
