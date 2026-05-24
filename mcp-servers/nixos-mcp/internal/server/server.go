package server

import (
	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"

	"github.com/lucawalz/vigil/mcp-servers/nixos-mcp/internal/config"
	"github.com/lucawalz/vigil/mcp-servers/nixos-mcp/internal/nixos"
)

type TextResult struct {
	Text string `json:"text" jsonschema:"Output text"`
}

func NewServer(client nixos.NixOSClient, cfg *config.Config) *server.MCPServer {
	s := server.NewMCPServer("nixos-mcp", "1.0.0",
		server.WithToolCapabilities(true),
	)

	s.AddTool(
		mcp.NewTool("get_generations",
			mcp.WithDescription("List NixOS generations on a remote host"),
			mcp.WithString("host", mcp.Required(), mcp.Description("Target hostname or IP")),
			mcp.WithOutputSchema[TextResult](),
		),
		nixos.HandleGetGenerations(client, cfg.MaxOutputBytesDescribe),
	)

	s.AddTool(
		mcp.NewTool("switch_generation",
			mcp.WithDescription("Switch to a specific NixOS generation on a remote host"),
			mcp.WithString("host", mcp.Required(), mcp.Description("Target hostname or IP")),
			mcp.WithNumber("generation", mcp.Required(), mcp.Description("Generation number to switch to")),
			mcp.WithOutputSchema[TextResult](),
		),
		nixos.HandleSwitchGeneration(client, cfg.MaxOutputBytesDescribe),
	)

	s.AddTool(
		mcp.NewTool("rebuild_test",
			mcp.WithDescription("Run nixos-rebuild test and return health gate status (dead-man's switch entry)"),
			mcp.WithString("host", mcp.Required(), mcp.Description("Target hostname or IP")),
			mcp.WithOutputSchema[TextResult](),
		),
		nixos.HandleRebuildTest(client, cfg.MaxOutputBytesDescribe),
	)

	s.AddTool(
		mcp.NewTool("get_journal",
			mcp.WithDescription("Get systemd journal entries for a unit on a remote host"),
			mcp.WithString("host", mcp.Required(), mcp.Description("Target hostname or IP")),
			mcp.WithString("unit", mcp.Required(), mcp.Description("Systemd unit name")),
			mcp.WithNumber("lines", mcp.Description("Number of log lines (default 100)")),
			mcp.WithOutputSchema[TextResult](),
		),
		nixos.HandleGetJournal(client, cfg.MaxOutputBytesLogs),
	)

	s.AddTool(
		mcp.NewTool("get_systemd_status",
			mcp.WithDescription("Get systemd unit status on a remote host"),
			mcp.WithString("host", mcp.Required(), mcp.Description("Target hostname or IP")),
			mcp.WithString("unit", mcp.Required(), mcp.Description("Systemd unit name")),
			mcp.WithOutputSchema[TextResult](),
		),
		nixos.HandleGetSystemdStatus(client, cfg.MaxOutputBytesDescribe),
	)

	s.AddTool(
		mcp.NewTool("etcd_snapshot_save",
			mcp.WithDescription("Save an etcd snapshot on a remote host"),
			mcp.WithString("host", mcp.Required(), mcp.Description("Target hostname or IP")),
			mcp.WithString("dest_path", mcp.Required(), mcp.Description("Destination path for the snapshot")),
			mcp.WithOutputSchema[TextResult](),
		),
		nixos.HandleEtcdSnapshotSave(client, cfg.MaxOutputBytesDescribe),
	)

	s.AddTool(
		mcp.NewTool("get_nix_path",
			mcp.WithDescription("Return repo-relative NixOS config path for a known hostname"),
			mcp.WithString("hostname", mcp.Required(), mcp.Description("NixOS host name e.g. hetzner-master")),
			mcp.WithOutputSchema[TextResult](),
		),
		nixos.HandleGetNixPath(client, cfg.MaxOutputBytesDescribe),
	)

	s.AddTool(
		mcp.NewTool("dry_build",
			mcp.WithDescription("Run nixos-rebuild dry-activate on a host and return the pending activation diff"),
			mcp.WithString("host", mcp.Required(), mcp.Description("Target hostname or IP")),
			mcp.WithOutputSchema[TextResult](),
		),
		nixos.HandleDryBuild(client, cfg.MaxOutputBytesDescribe),
	)

	s.AddTool(
		mcp.NewTool("trigger_reconcile",
			mcp.WithDescription("Start vigil-auto-reconcile.service on a host (fire-and-forget)"),
			mcp.WithString("host", mcp.Required(), mcp.Description("Target hostname or IP")),
			mcp.WithOutputSchema[TextResult](),
		),
		nixos.HandleTriggerReconcile(client, cfg.MaxOutputBytesDescribe),
	)

	return s
}
