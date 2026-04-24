# LLM Provider Selection

## Evaluation Models

The vigil evaluation campaign uses 3 models: Qwen3 Coder and DeepSeek V3.1 via Ollama Cloud, and Claude Sonnet 4.6 via Anthropic API.

| Model | Provider | Tag | Parameters | Context Window | Selection Rationale |
|-------|----------|-----|-----------|----------------|---------------------|
| Qwen3 Coder | Ollama Cloud | `qwen3-coder-next:cloud` | 480B MoE (35B active) | 256K | Strongest code generation and tool-use capability; MoE efficiency matches SRE tool-call-heavy workloads |
| DeepSeek V3.2 | Ollama Cloud | `deepseek-v3.2:cloud` | 671B MoE | 128K | Strong multi-step reasoning for complex diagnostic chains |
| Claude Sonnet 4.6 | Anthropic API | `claude-sonnet-4-6` | — | 200K | Upper-bound reference; state-of-the-art tool use and agentic reasoning |

## Selection Criteria

Each model must satisfy:

1. **SRE-task reasoning quality** — ability to interpret Kubernetes and NixOS diagnostics, formulate multi-step remediation plans, and use MCP tools correctly
2. **Context window >= 32K tokens** — sufficient for fault evidence, tool call history, and agent conversation within a single diagnosis-remediation cycle

## Provider Configuration

All models are accessed via the OpenAI-compatible API interface. Switch between providers by changing environment variables:

| Provider | LLM_BASE_URL | LLM_MODEL_NAME | Use Case |
|----------|-------------|----------------|----------|
| Groq | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` | Development iteration (free tier) |
| Ollama Cloud | `https://api.ollama.com/v1` | `qwen3-coder-next:cloud` | Evaluation campaign |
| Anthropic | `https://api.anthropic.com/v1` | `claude-sonnet-4-6` | Reference model evaluation |

Set `LLM_API_KEY` to the corresponding provider API key for each configuration.
