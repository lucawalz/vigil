package k8s

import (
	"context"
	"fmt"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
)

func HandleGetNodes(client K8sClient, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		output, err := client.GetNodes(ctx)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("GetNodes: %v", err)), nil
		}
		return mcp.NewToolResultText(truncateOutput(output, maxBytes)), nil
	}
}

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
