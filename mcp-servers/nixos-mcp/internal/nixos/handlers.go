package nixos

import (
	"context"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
)

const (
	hintGetGenerations   = "verify the host is reachable via SSH and NixOS is running"
	hintStageGeneration  = "try get_generations to list available generations first"
	hintCommitGeneration = "stage a generation first so the bootloader has a tested target to commit"
	hintRebuildTest      = "check get_nix_path to verify the NixOS flake configuration is accessible"
	hintGetJournal       = "verify the systemd unit name with get_systemd_status first"
	hintGetSystemdStatus = "try get_journal for the unit to see recent log output"
	hintGetSysctl        = "verify the sysctl key exists, e.g. net.bridge.bridge-nf-call-iptables"
	hintEtcdSnapshotSave = "verify the dest_path directory is writable and etcd is running on the host"
	hintGetNixPath       = "verify the hostname matches a NixOS configuration in the flake"
	hintDryBuild         = "check get_nix_path to verify the configuration path, then fix Nix syntax errors"
	hintTriggerReconcile = "verify the host is reachable and the NixOS agent service is running"
)

func HandleGetGenerations(client NixOSClient, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		host, ok := req.GetArguments()["host"].(string)
		if !ok || host == "" {
			return mcp.NewToolResultError("host: missing or wrong type"), nil
		}
		out, err := client.GetGenerations(ctx, host)
		if err != nil {
			return toolError("GetGenerations", err.Error(), hintGetGenerations), nil
		}
		return mcp.NewToolResultText(truncateOutput(out, maxBytes)), nil
	}
}

func HandleStageGeneration(client NixOSClient, maxBytes int) server.ToolHandlerFunc {
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
		out, err := client.StageGeneration(ctx, host, int(genFloat))
		if err != nil {
			return toolError("StageGeneration", err.Error(), hintStageGeneration), nil
		}
		return mcp.NewToolResultText(truncateOutput(out, maxBytes)), nil
	}
}

func HandleCommitGeneration(client NixOSClient, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		host, ok := req.GetArguments()["host"].(string)
		if !ok || host == "" {
			return mcp.NewToolResultError("host: missing or wrong type"), nil
		}
		out, err := client.CommitGeneration(ctx, host)
		if err != nil {
			return toolError("CommitGeneration", err.Error(), hintCommitGeneration), nil
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
			return toolError("RebuildTest", err.Error(), hintRebuildTest), nil
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
		unit, _ := args["unit"].(string)
		lines := 100
		if lf, ok := args["lines"].(float64); ok {
			lines = int(lf)
		}
		out, err := client.GetJournal(ctx, host, unit, lines)
		if err != nil {
			return toolError("GetJournal", err.Error(), hintGetJournal), nil
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
			return toolError("GetSystemdStatus", err.Error(), hintGetSystemdStatus), nil
		}
		return mcp.NewToolResultText(truncateOutput(out, maxBytes)), nil
	}
}

func HandleGetSysctl(client NixOSClient, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		host, ok := args["host"].(string)
		if !ok || host == "" {
			return mcp.NewToolResultError("host: missing or wrong type"), nil
		}
		key, ok := args["key"].(string)
		if !ok || key == "" {
			return mcp.NewToolResultError("key: missing or wrong type"), nil
		}
		out, err := client.GetSysctl(ctx, host, key)
		if err != nil {
			return toolError("GetSysctl", err.Error(), hintGetSysctl), nil
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
			return toolError("EtcdSnapshotSave", err.Error(), hintEtcdSnapshotSave), nil
		}
		return mcp.NewToolResultText(truncateOutput(out, maxBytes)), nil
	}
}

func HandleGetNixPath(client NixOSClient, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		hostname, ok := args["hostname"].(string)
		if !ok || hostname == "" {
			return mcp.NewToolResultError("hostname: missing or wrong type"), nil
		}
		out, err := client.GetNixPath(ctx, hostname)
		if err != nil {
			return toolError("GetNixPath", err.Error(), hintGetNixPath), nil
		}
		return mcp.NewToolResultText(truncateOutput(out, maxBytes)), nil
	}
}

func HandleDryBuild(client NixOSClient, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		host, ok := args["host"].(string)
		if !ok || host == "" {
			return mcp.NewToolResultError("host: missing or wrong type"), nil
		}
		out, err := client.DryBuild(ctx, host)
		if err != nil {
			return toolError("DryBuild", err.Error(), hintDryBuild), nil
		}
		return mcp.NewToolResultText(truncateOutput(out, maxBytes)), nil
	}
}

func HandleTriggerReconcile(client NixOSClient, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		host, ok := args["host"].(string)
		if !ok || host == "" {
			return mcp.NewToolResultError("host: missing or wrong type"), nil
		}
		out, err := client.TriggerReconcile(ctx, host)
		if err != nil {
			return toolError("TriggerReconcile", err.Error(), hintTriggerReconcile), nil
		}
		return mcp.NewToolResultText(truncateOutput(out, maxBytes)), nil
	}
}
