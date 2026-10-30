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

var ErrHeadMoved = errors.New("head moved since the gate ran")

var errNoGatedHead = errors.New("no gated head SHA to pin the merge to")

func protectedBranchError(what, branch string) *mcp.CallToolResult {
	return toolError(what, fmt.Sprintf("%s: %s", ErrProtectedBranch.Error(), branch), hintProtectedBranch)
}
