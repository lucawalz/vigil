package flux

import (
	"context"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
)

const (
	hintReconcileKustomization = "try get_kustomization_status to check current state before reconciling"
	hintGetKustomizationStatus = "verify the Flux Kustomization exists; check kubectl get kustomization -n <namespace>"
	hintGetGitRepositoryStatus = "verify the Flux GitRepository exists and the source-controller pod is healthy"
)

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
			return toolError("ReconcileKustomization", err.Error(), hintReconcileKustomization), nil
		}
		return mcp.NewToolResultText(truncateOutput(result, maxBytes)), nil
	}
}

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
			return toolError("GetKustomizationStatus", err.Error(), hintGetKustomizationStatus), nil
		}
		return mcp.NewToolResultText(truncateOutput(result, maxBytes)), nil
	}
}

func HandleGetGitRepositoryStatus(client FluxClient, maxBytes int) server.ToolHandlerFunc {
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
		result, err := client.GetGitRepositoryStatus(ctx, ns, name)
		if err != nil {
			return toolError("GetGitRepositoryStatus", err.Error(), hintGetGitRepositoryStatus), nil
		}
		return mcp.NewToolResultText(truncateOutput(result, maxBytes)), nil
	}
}
