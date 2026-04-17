package flux

import (
	"context"
	"fmt"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
)

// HandleSuspendKustomization suspends a Flux Kustomization and calls onSuspend to
// register the name with the session guard in server.go.
func HandleSuspendKustomization(client FluxClient, onSuspend func(name string)) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		ns, ok := args["namespace"].(string)
		if !ok || ns == "" {
			return mcp.NewToolResultError("namespace: missing or wrong type"), nil
		}
		name, ok := args["name"].(string)
		if !ok || name == "" {
			return mcp.NewToolResultError("name: missing or wrong type"), nil
		}
		if err := client.SuspendKustomization(ctx, ns, name); err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("SuspendKustomization: %v", err)), nil
		}
		onSuspend(name)
		return mcp.NewToolResultText(fmt.Sprintf("kustomization %s/%s suspended", ns, name)), nil
	}
}

// HandleResumeKustomization resumes a Flux Kustomization and calls onResume to
// unregister the name from the session guard.
func HandleResumeKustomization(client FluxClient, onResume func(name string) bool) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		ns, ok := args["namespace"].(string)
		if !ok || ns == "" {
			return mcp.NewToolResultError("namespace: missing or wrong type"), nil
		}
		name, ok := args["name"].(string)
		if !ok || name == "" {
			return mcp.NewToolResultError("name: missing or wrong type"), nil
		}
		if err := client.ResumeKustomization(ctx, ns, name); err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("ResumeKustomization: %v", err)), nil
		}
		onResume(name)
		return mcp.NewToolResultText(fmt.Sprintf("kustomization %s/%s resumed", ns, name)), nil
	}
}

// HandleReconcileKustomization triggers reconciliation. Guard is applied by server.go.
func HandleReconcileKustomization(client FluxClient, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		ns, ok := args["namespace"].(string)
		if !ok || ns == "" {
			return mcp.NewToolResultError("namespace: missing or wrong type"), nil
		}
		name, ok := args["name"].(string)
		if !ok || name == "" {
			return mcp.NewToolResultError("name: missing or wrong type"), nil
		}
		result, err := client.ReconcileKustomization(ctx, ns, name)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("ReconcileKustomization: %v", err)), nil
		}
		return mcp.NewToolResultText(truncateOutput(result, maxBytes)), nil
	}
}

// HandleGetKustomizationStatus returns Flux Kustomization status. No guard required.
func HandleGetKustomizationStatus(client FluxClient, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		ns, ok := args["namespace"].(string)
		if !ok || ns == "" {
			return mcp.NewToolResultError("namespace: missing or wrong type"), nil
		}
		name, ok := args["name"].(string)
		if !ok || name == "" {
			return mcp.NewToolResultError("name: missing or wrong type"), nil
		}
		result, err := client.GetKustomizationStatus(ctx, ns, name)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("GetKustomizationStatus: %v", err)), nil
		}
		return mcp.NewToolResultText(truncateOutput(result, maxBytes)), nil
	}
}
