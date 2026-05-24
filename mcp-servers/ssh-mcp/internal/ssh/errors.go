package ssh

import "github.com/mark3labs/mcp-go/mcp"

func toolError(what, why, hint string) *mcp.CallToolResult {
	msg := what + ": " + why
	if hint != "" {
		msg += ". Hint: " + hint
	}
	return mcp.NewToolResultError(msg)
}
