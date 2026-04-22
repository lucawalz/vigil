package k8s

import (
	"context"
	"fmt"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
)

func HandleGetPods(client K8sClient, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		ns, ok := args["namespace"].(string)
		if !ok || ns == "" {
			return mcp.NewToolResultError("namespace: missing or wrong type"), nil
		}
		output, err := client.GetPods(ctx, ns)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("GetPods: %v", err)), nil
		}
		return mcp.NewToolResultText(truncateOutput(output, maxBytes)), nil
	}
}

func HandleDescribePod(client K8sClient, maxBytes int) server.ToolHandlerFunc {
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
		output, err := client.DescribePod(ctx, ns, name)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("DescribePod: %v", err)), nil
		}
		return mcp.NewToolResultText(truncateOutput(output, maxBytes)), nil
	}
}

func HandleGetLogs(client K8sClient, maxBytes int) server.ToolHandlerFunc {
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
		container, ok := args["container"].(string)
		if !ok || container == "" {
			return mcp.NewToolResultError("container: missing or wrong type"), nil
		}
		var tailLines int64 = 100
		if f, ok := args["tail_lines"].(float64); ok && f > 0 {
			tailLines = int64(f)
		}
		output, err := client.GetLogs(ctx, ns, name, container, tailLines)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("GetLogs: %v", err)), nil
		}
		return mcp.NewToolResultText(truncateOutput(output, maxBytes)), nil
	}
}

func HandleRolloutUndo(client K8sClient, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		ns, ok := args["namespace"].(string)
		if !ok || ns == "" {
			return mcp.NewToolResultError("namespace: missing or wrong type"), nil
		}
		deployment, ok := args["deployment"].(string)
		if !ok || deployment == "" {
			return mcp.NewToolResultError("deployment: missing or wrong type"), nil
		}
		output, err := client.RolloutUndo(ctx, ns, deployment)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("RolloutUndo: %v", err)), nil
		}
		return mcp.NewToolResultText(truncateOutput(output, maxBytes)), nil
	}
}

func HandleApplyPatch(client K8sClient, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		ns, ok := args["namespace"].(string)
		if !ok || ns == "" {
			return mcp.NewToolResultError("namespace: missing or wrong type"), nil
		}
		resourceType, ok := args["resource_type"].(string)
		if !ok || resourceType == "" {
			return mcp.NewToolResultError("resource_type: missing or wrong type"), nil
		}
		name, ok := args["name"].(string)
		if !ok || name == "" {
			return mcp.NewToolResultError("name: missing or wrong type"), nil
		}
		patch, ok := args["patch"].(string)
		if !ok || patch == "" {
			return mcp.NewToolResultError("patch: missing or wrong type"), nil
		}
		output, err := client.ApplyPatch(ctx, ns, resourceType, name, patch)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("ApplyPatch: %v", err)), nil
		}
		return mcp.NewToolResultText(truncateOutput(output, maxBytes)), nil
	}
}

func HandleRolloutStatus(client K8sClient, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		ns, ok := args["namespace"].(string)
		if !ok || ns == "" {
			return mcp.NewToolResultError("namespace: missing or wrong type"), nil
		}
		deployment, ok := args["deployment"].(string)
		if !ok || deployment == "" {
			return mcp.NewToolResultError("deployment: missing or wrong type"), nil
		}
		output, err := client.RolloutStatus(ctx, ns, deployment)
		if err != nil {
			return mcp.NewToolResultText(fmt.Sprintf("RolloutStatus: %v", err)), nil
		}
		return mcp.NewToolResultText(truncateOutput(output, maxBytes)), nil
	}
}
