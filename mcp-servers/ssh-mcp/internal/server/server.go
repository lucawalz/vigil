package server

import (
	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"

	"github.com/lucawalz/vigil/mcp-servers/ssh-mcp/internal/config"
	"github.com/lucawalz/vigil/mcp-servers/ssh-mcp/internal/ssh"
)

type TextResult struct {
	Text string `json:"text" jsonschema:"Output text"`
}

func NewServer(client ssh.SSHClient, cfg *config.Config) *server.MCPServer {
	s := server.NewMCPServer("ssh-mcp", "1.0.0",
		server.WithToolCapabilities(true),
	)

	s.AddTool(
		mcp.NewTool("run_allowed_command",
			mcp.WithDescription("Run a diagnostic command on a remote host via the static allow-list"),
			mcp.WithString("host",
				mcp.Required(),
				mcp.Description("Target hostname or IP address"),
			),
			mcp.WithString("binary",
				mcp.Required(),
				mcp.Description("Command binary name (must be in the allow-list)"),
			),
			mcp.WithArray("args",
				mcp.Description("Command arguments"),
			),
			mcp.WithOutputSchema[TextResult](),
		),
		ssh.HandleRunAllowedCommand(client, cfg.MaxOutputBytesDescribe),
	)

	return s
}
