package ssh

import (
	"context"
	"fmt"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
)

func HandleRunAllowedCommand(client SSHClient, maxBytes int) server.ToolHandlerFunc {
	return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()

		host, ok := args["host"].(string)
		if !ok || host == "" {
			return mcp.NewToolResultError("host: missing or wrong type"), nil
		}

		binary, ok := args["binary"].(string)
		if !ok || binary == "" {
			return mcp.NewToolResultError("binary: missing or wrong type"), nil
		}

		var stringArgs []string
		if rawArgs, ok := args["args"].([]any); ok {
			for _, v := range rawArgs {
				s, ok := v.(string)
				if !ok {
					return mcp.NewToolResultError(fmt.Sprintf("args: element %v is not a string", v)), nil
				}
				stringArgs = append(stringArgs, s)
			}
		}

		if err := validateCommand(binary, stringArgs); err != nil {
			return mcp.NewToolResultError(err.Error()), nil
		}

		output, err := client.RunAllowedCommand(ctx, host, binary, stringArgs)
		if err != nil {
			return mcp.NewToolResultError(fmt.Sprintf("RunAllowedCommand: %v", err)), nil
		}
		return mcp.NewToolResultText(truncateOutput(output, maxBytes)), nil
	}
}
