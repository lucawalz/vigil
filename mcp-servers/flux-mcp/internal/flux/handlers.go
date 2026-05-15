package flux

import (
	"context"
	"fmt"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
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
			return mcp.NewToolResultError(fmt.Sprintf("ReconcileKustomization: %v", err)), nil
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
			return mcp.NewToolResultError(fmt.Sprintf("GetKustomizationStatus: %v", err)), nil
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
			return mcp.NewToolResultError(fmt.Sprintf("GetGitRepositoryStatus: %v", err)), nil
		}
		return mcp.NewToolResultText(truncateOutput(result, maxBytes)), nil
	}
}
