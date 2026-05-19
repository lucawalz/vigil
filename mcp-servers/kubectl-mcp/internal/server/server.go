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
		mcp.NewTool("get_nodes",
			mcp.WithDescription("List all nodes and their Ready status"),
		),
		k8s.HandleGetNodes(client, cfg.MaxOutputBytesDescribe),
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

	s.AddTool(
		mcp.NewTool("get_events",
			mcp.WithDescription("List events filtered by field selector"),
			mcp.WithString("namespace",
				mcp.Required(),
				mcp.Description("Kubernetes namespace"),
			),
			mcp.WithString("field_selector",
				mcp.Description("Field selector e.g. reason=FailedScheduling"),
			),
		),
		k8s.HandleGetEvents(client, cfg.MaxOutputBytesDescribe),
	)

	s.AddTool(
		mcp.NewTool("describe_node",
			mcp.WithDescription("Get detailed description of a node"),
			mcp.WithString("name",
				mcp.Required(),
				mcp.Description("Node name"),
			),
		),
		k8s.HandleDescribeNode(client, cfg.MaxOutputBytesDescribe),
	)

	s.AddTool(
		mcp.NewTool("get_taints",
			mcp.WithDescription("Get taints on a node"),
			mcp.WithString("node",
				mcp.Required(),
				mcp.Description("Node name"),
			),
		),
		k8s.HandleGetTaints(client, cfg.MaxOutputBytesDescribe),
	)

	s.AddTool(
		mcp.NewTool("delete_resource",
			mcp.WithDescription("Delete a Kubernetes resource by kind, namespace, and name"),
			mcp.WithString("kind",
				mcp.Required(),
				mcp.Description("Resource kind e.g. Deployment, Pod, StatefulSet"),
			),
			mcp.WithString("namespace",
				mcp.Required(),
				mcp.Description("Kubernetes namespace"),
			),
			mcp.WithString("name",
				mcp.Required(),
				mcp.Description("Resource name"),
			),
		),
		k8s.HandleDeleteResource(client, cfg.MaxOutputBytesDescribe),
	)

	s.AddTool(
		mcp.NewTool("get_resource_yaml",
			mcp.WithDescription("Get live YAML for any Kubernetes resource (system fields stripped)"),
			mcp.WithString("kind",
				mcp.Required(),
				mcp.Description("Resource kind e.g. Deployment, ConfigMap, HorizontalPodAutoscaler"),
			),
			mcp.WithString("namespace",
				mcp.Required(),
				mcp.Description("Kubernetes namespace (empty string for cluster-scoped resources)"),
			),
			mcp.WithString("name",
				mcp.Required(),
				mcp.Description("Resource name"),
			),
		),
		k8s.HandleGetResourceYaml(client, cfg.MaxOutputBytesDescribe),
	)

	return s
}
