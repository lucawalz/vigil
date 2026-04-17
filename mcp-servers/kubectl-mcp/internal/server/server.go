package server

import (
	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"

	"github.com/lucawalz/vigil/mcp-servers/kubectl-mcp/internal/config"
	"github.com/lucawalz/vigil/mcp-servers/kubectl-mcp/internal/k8s"
)

func NewServer(client k8s.K8sClient, cfg *config.Config) *server.MCPServer {
	s := server.NewMCPServer("kubectl-mcp", "1.0.0",
		server.WithToolCapabilities(true),
	)

	s.AddTool(
		mcp.NewTool("get_pods",
			mcp.WithDescription("List all pods in a namespace"),
			mcp.WithString("namespace",
				mcp.Required(),
				mcp.Description("Kubernetes namespace"),
			),
		),
		k8s.HandleGetPods(client, cfg.MaxOutputBytesDescribe),
	)

	s.AddTool(
		mcp.NewTool("describe_pod",
			mcp.WithDescription("Get detailed description of a pod"),
			mcp.WithString("namespace",
				mcp.Required(),
				mcp.Description("Kubernetes namespace"),
			),
			mcp.WithString("name",
				mcp.Required(),
				mcp.Description("Pod name"),
			),
		),
		k8s.HandleDescribePod(client, cfg.MaxOutputBytesDescribe),
	)

	s.AddTool(
		mcp.NewTool("get_logs",
			mcp.WithDescription("Get logs from a pod container"),
			mcp.WithString("namespace",
				mcp.Required(),
				mcp.Description("Kubernetes namespace"),
			),
			mcp.WithString("name",
				mcp.Required(),
				mcp.Description("Pod name"),
			),
			mcp.WithString("container",
				mcp.Required(),
				mcp.Description("Container name"),
			),
			mcp.WithNumber("tail_lines",
				mcp.Description("Number of lines to tail (default 100)"),
			),
		),
		k8s.HandleGetLogs(client, cfg.MaxOutputBytesLogs),
	)

	s.AddTool(
		mcp.NewTool("rollout_undo",
			mcp.WithDescription("Rollback a deployment to its previous revision"),
			mcp.WithString("namespace",
				mcp.Required(),
				mcp.Description("Kubernetes namespace"),
			),
			mcp.WithString("deployment",
				mcp.Required(),
				mcp.Description("Deployment name"),
			),
		),
		k8s.HandleRolloutUndo(client, cfg.MaxOutputBytesDescribe),
	)

	s.AddTool(
		mcp.NewTool("apply_patch",
			mcp.WithDescription("Apply a strategic merge patch to a resource"),
			mcp.WithString("namespace",
				mcp.Required(),
				mcp.Description("Kubernetes namespace"),
			),
			mcp.WithString("resource_type",
				mcp.Required(),
				mcp.Description("Resource type (e.g. deployment, statefulset)"),
			),
			mcp.WithString("name",
				mcp.Required(),
				mcp.Description("Resource name"),
			),
			mcp.WithString("patch",
				mcp.Required(),
				mcp.Description("JSON merge patch body"),
			),
		),
		k8s.HandleApplyPatch(client, cfg.MaxOutputBytesDescribe),
	)

	s.AddTool(
		mcp.NewTool("rollout_status",
			mcp.WithDescription("Get rollout status of a deployment"),
			mcp.WithString("namespace",
				mcp.Required(),
				mcp.Description("Kubernetes namespace"),
			),
			mcp.WithString("deployment",
				mcp.Required(),
				mcp.Description("Deployment name"),
			),
		),
		k8s.HandleRolloutStatus(client, cfg.MaxOutputBytesDescribe),
	)

	return s
}
