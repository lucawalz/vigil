package ssh_test

import (
	"context"
	"fmt"
	"strings"
	"testing"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/mcptest"
	"github.com/mark3labs/mcp-go/server"

	internalssh "github.com/lucawalz/vigil/mcp-servers/ssh-mcp/internal/ssh"
)

// fakeSSHClient implements SSHClient and records what was called.
type fakeSSHClient struct {
	output     string
	err        error
	lastHost   string
	lastBinary string
	lastArgs   []string
}

func (f *fakeSSHClient) RunAllowedCommand(_ context.Context, host, binary string, args []string) (string, error) {
	f.lastHost = host
	f.lastBinary = binary
	f.lastArgs = args
	return f.output, f.err
}

func newTestServer(t *testing.T, client internalssh.SSHClient, maxBytes int) *mcptest.Server {
	t.Helper()
	srv, err := mcptest.NewServer(t, server.ServerTool{
		Tool: mcp.NewTool("run_allowed_command",
			mcp.WithDescription("Run a diagnostic command on a remote host via the static allow-list"),
			mcp.WithString("host", mcp.Required()),
			mcp.WithString("binary", mcp.Required()),
		),
		Handler: internalssh.HandleRunAllowedCommand(client, maxBytes),
	})
	if err != nil {
		t.Fatal(err)
	}
	return srv
}

func callTool(t *testing.T, srv *mcptest.Server, toolArgs map[string]any) *mcp.CallToolResult {
	t.Helper()
	var req mcp.CallToolRequest
	req.Params.Name = "run_allowed_command"
	req.Params.Arguments = toolArgs
	result, err := srv.Client().CallTool(context.Background(), req)
	if err != nil {
		t.Fatalf("CallTool: %v", err)
	}
	return result
}

func resultText(result *mcp.CallToolResult) string {
	if len(result.Content) == 0 {
		return ""
	}
	if tc, ok := result.Content[0].(mcp.TextContent); ok {
		return tc.Text
	}
	return ""
}

func TestRunAllowedCommandHandler_Success(t *testing.T) {
	fake := &fakeSSHClient{output: "output text"}
	srv := newTestServer(t, fake, 4096)
	defer srv.Close()

	result := callTool(t, srv, map[string]any{
		"host":   "192.168.1.10",
		"binary": "uptime",
	})

	if result.IsError {
		t.Errorf("expected success, got IsError=true: %s", resultText(result))
	}
	if !strings.Contains(resultText(result), "output text") {
		t.Errorf("expected 'output text' in response, got: %s", resultText(result))
	}
}

func TestRunAllowedCommandHandler_Truncation(t *testing.T) {
	oversized := strings.Repeat("diagnostic-line\n", 1000) // well over 4096 bytes
	fake := &fakeSSHClient{output: oversized}
	srv := newTestServer(t, fake, 4096)
	defer srv.Close()

	result := callTool(t, srv, map[string]any{
		"host":   "192.168.1.10",
		"binary": "journalctl",
	})

	if result.IsError {
		t.Errorf("unexpected error: %s", resultText(result))
	}
	if !strings.Contains(resultText(result), "[TRUNCATED:") {
		t.Errorf("expected truncation marker, got: %.100s", resultText(result))
	}
}

func TestRunAllowedCommandHandler_RejectedCommand(t *testing.T) {
	fake := &fakeSSHClient{}
	srv := newTestServer(t, fake, 4096)
	defer srv.Close()

	result := callTool(t, srv, map[string]any{
		"host":   "192.168.1.10",
		"binary": "rm",
		"args":   []any{"-rf", "/"},
	})

	if !result.IsError {
		t.Error("expected IsError=true for rejected command")
	}
	if !strings.Contains(resultText(result), "allow-list") {
		t.Errorf("expected 'allow-list' in error text, got: %s", resultText(result))
	}
}

func TestRunAllowedCommandHandler_ShellInjection(t *testing.T) {
	fake := &fakeSSHClient{}
	srv := newTestServer(t, fake, 4096)
	defer srv.Close()

	result := callTool(t, srv, map[string]any{
		"host":   "192.168.1.10",
		"binary": "journalctl",
		"args":   []any{"-u", "k3s; rm -rf /"},
	})

	if !result.IsError {
		t.Error("expected IsError=true for shell injection attempt")
	}
	if !strings.Contains(resultText(result), "metacharacter") {
		t.Errorf("expected 'metacharacter' in error text, got: %s", resultText(result))
	}
}

func TestRunAllowedCommandHandler_MissingHost(t *testing.T) {
	fake := &fakeSSHClient{}
	srv := newTestServer(t, fake, 4096)
	defer srv.Close()

	result := callTool(t, srv, map[string]any{
		"binary": "uptime",
	})

	if !result.IsError {
		t.Error("expected IsError=true for missing host argument")
	}
}

func TestRunAllowedCommandHandler_DomainError(t *testing.T) {
	fake := &fakeSSHClient{err: fmt.Errorf("connection refused")}
	srv := newTestServer(t, fake, 4096)
	defer srv.Close()

	result := callTool(t, srv, map[string]any{
		"host":   "192.168.1.10",
		"binary": "uptime",
	})

	if !result.IsError {
		t.Error("expected IsError=true for domain error")
	}
}
