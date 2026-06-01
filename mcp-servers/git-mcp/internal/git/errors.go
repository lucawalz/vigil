package git

import (
	"errors"
	"fmt"

	"github.com/mark3labs/mcp-go/mcp"
)

func toolError(what, why, hint string) *mcp.CallToolResult {
	msg := what + ": " + why
	if hint != "" {
		msg += ". Hint: " + hint
	}
	return mcp.NewToolResultError(msg)
}

var ErrProtectedBranch = errors.New("branch is protected")

func protectedBranchError(what, branch string) *mcp.CallToolResult {
	return toolError(what, fmt.Sprintf("%s: %s", ErrProtectedBranch.Error(), branch), hintProtectedBranch)
}
