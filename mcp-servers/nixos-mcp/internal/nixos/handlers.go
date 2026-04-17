package nixos

import (
	"context"
	"fmt"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
)

func HandleGetGenerations(client NixOSClient, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		host, ok := req.GetArguments()["host"].(string)
		if !ok || host == "" {
			return mcp.NewToolResultError("host: missing or wrong type"), nil
		}
		out, err := client.GetGenerations(ctx, host)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("GetGenerations: %v", err)), nil
		}
		return mcp.NewToolResultText(truncateOutput(out, maxBytes)), nil
	}
}

func HandleSwitchGeneration(client NixOSClient, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		host, ok := args["host"].(string)
		if !ok || host == "" {
			return mcp.NewToolResultError("host: missing or wrong type"), nil
		}
		genFloat, ok := args["generation"].(float64)
		if !ok {
			return mcp.NewToolResultError("generation: missing or wrong type"), nil
		}
		out, err := client.SwitchGeneration(ctx, host, int(genFloat))
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("SwitchGeneration: %v", err)), nil
		}
		return mcp.NewToolResultText(truncateOutput(out, maxBytes)), nil
	}
}

func HandleRebuildTest(client NixOSClient, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		host, ok := req.GetArguments()["host"].(string)
		if !ok || host == "" {
			return mcp.NewToolResultError("host: missing or wrong type"), nil
		}
		out, err := client.RebuildTest(ctx, host)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("RebuildTest: %v", err)), nil
		}
		return mcp.NewToolResultText(truncateOutput(out, maxBytes)), nil
	}
}

func HandleGetJournal(client NixOSClient, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		host, ok := args["host"].(string)
		if !ok || host == "" {
			return mcp.NewToolResultError("host: missing or wrong type"), nil
		}
		unit, ok := args["unit"].(string)
		if !ok || unit == "" {
			return mcp.NewToolResultError("unit: missing or wrong type"), nil
		}
		lines := 100
		if lf, ok := args["lines"].(float64); ok {
			lines = int(lf)
		}
		out, err := client.GetJournal(ctx, host, unit, lines)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("GetJournal: %v", err)), nil
		}
		return mcp.NewToolResultText(truncateOutput(out, maxBytes)), nil
	}
}

func HandleGetSystemdStatus(client NixOSClient, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		host, ok := args["host"].(string)
		if !ok || host == "" {
			return mcp.NewToolResultError("host: missing or wrong type"), nil
		}
		unit, ok := args["unit"].(string)
		if !ok || unit == "" {
			return mcp.NewToolResultError("unit: missing or wrong type"), nil
		}
		out, err := client.GetSystemdStatus(ctx, host, unit)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("GetSystemdStatus: %v", err)), nil
		}
		return mcp.NewToolResultText(truncateOutput(out, maxBytes)), nil
	}
}

func HandleEtcdSnapshotSave(client NixOSClient, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		host, ok := args["host"].(string)
		if !ok || host == "" {
			return mcp.NewToolResultError("host: missing or wrong type"), nil
		}
		destPath, ok := args["dest_path"].(string)
		if !ok || destPath == "" {
			return mcp.NewToolResultError("dest_path: missing or wrong type"), nil
		}
		out, err := client.EtcdSnapshotSave(ctx, host, destPath)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("EtcdSnapshotSave: %v", err)), nil
		}
		return mcp.NewToolResultText(truncateOutput(out, maxBytes)), nil
	}
}
