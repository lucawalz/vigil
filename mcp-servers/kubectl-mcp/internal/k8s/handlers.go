package k8s

import (
	"context"
	"fmt"
	"strings"

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
		prefix, events := splitEventsSection(output)
		return mcp.NewToolResultText(truncateOutput(prefix, maxBytes) + events), nil
	}
}

func splitEventsSection(s string) (prefix, events string) {
	const delimiter = "\nEvents:"
	idx := strings.LastIndex(s, delimiter)
	if idx == -1 {
		return s, ""
	}
	return s[:idx], s[idx:]
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

func HandleGetEvents(client K8sClient, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		ns, ok := args["namespace"].(string)
		if !ok || ns == "" {
			return mcp.NewToolResultError("namespace: missing or wrong type"), nil
		}
		fs, _ := args["field_selector"].(string)
		output, err := client.GetEvents(ctx, ns, fs)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("GetEvents: %v", err)), nil
		}
		return mcp.NewToolResultText(truncateOutput(output, maxBytes)), nil
	}
}

func HandleDescribeNode(client K8sClient, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		name, ok := args["name"].(string)
		if !ok || name == "" {
			return mcp.NewToolResultError("name: missing or wrong type"), nil
		}
		output, err := client.DescribeNode(ctx, name)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("DescribeNode: %v", err)), nil
		}
		return mcp.NewToolResultText(truncateOutput(output, maxBytes)), nil
	}
}

func HandleGetTaints(client K8sClient, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		node, ok := args["node"].(string)
		if !ok || node == "" {
			return mcp.NewToolResultError("node: missing or wrong type"), nil
		}
		output, err := client.GetTaints(ctx, node)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("GetTaints: %v", err)), nil
		}
		return mcp.NewToolResultText(truncateOutput(output, maxBytes)), nil
	}
}

func HandleDeleteResource(client K8sClient, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		kind, ok := args["kind"].(string)
		if !ok || kind == "" {
			return mcp.NewToolResultError("kind: missing or wrong type"), nil
		}
		ns, ok := args["namespace"].(string)
		if !ok || ns == "" {
			return mcp.NewToolResultError("namespace: missing or wrong type"), nil
		}
		name, ok := args["name"].(string)
		if !ok || name == "" {
			return mcp.NewToolResultError("name: missing or wrong type"), nil
		}
		output, err := client.DeleteResource(ctx, kind, ns, name)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("DeleteResource: %v", err)), nil
		}
		return mcp.NewToolResultText(output), nil
	}
}
