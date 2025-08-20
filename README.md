# Orchestrator

A lightweight, Python-based CLI tool and library for protocol-agnostic agent orchestration—combining MCP (Model Context Protocol) and A2A (Agent-to-Agent) support with GPT-OSS reasoning.

## Features

- Dual-protocol orchestration: MCP for tools, A2A for agent collaboration  
- Intelligent reasoning engine powered by GPT-OSS (Hugging Face Inference)  
- Flexible CLI with mode flags (`--faves`, `--useful`, `--essential`), keyword filters (`--words`), and alias (`ts`)  
- AsyncIO-based drivers for STDIO/SSE (MCP) and HTTP/JSON-RPC (A2A)  
- Workflow engine with dependency management, retries, and state persistence  
- Enterprise-grade security: OAuth2/OpenID Connect, token management, TLS  
- Configurable via Pydantic models (YAML/JSON) and environment variables  
- Comprehensive testing, CI/CD, Docker packaging, and examples

## Installation

Requirements: Python ≥ 3.11, `uv` environment manager

```bash
# Clone repository
git clone https://github.com/yourorg/orchestrator.git
cd orchestrator

# Initialize `uv` environment and install dependencies
uv init
uv install

# Activate environment
uv shell
```

## Configuration

Copy `examples/config.yaml` to `~/.ts/config.yaml` and update:

```yaml
hf_api_key: YOUR_HUGGINGFACE_TOKEN
gpt_oss_model: openai/gpt-oss-20B

mcp_servers:
  - name: github
    command: ["npx", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_TOKEN: "YOUR_GITHUB_TOKEN"
  - name: shortcut
    command: ["npx", "@shortcut/mcp"]
    env:
      SHORTCUT_API_TOKEN: "YOUR_SHORTCUT_TOKEN"

a2a_endpoints:
  - name: k8s-agent
    url: https://agent.example.com/jsonrpc
    auth:
      token: "YOUR_AGENT_TOKEN"
```

Environment variables:

- `HF_API_KEY` — Hugging Face API token  
- `A2A_AUTH_TOKEN` — default token for A2A endpoints  

## Usage

Run the CLI via `ts`:

```bash
# Quick query with mode flags
ts q "Deploy microservice to AWS" -ef

# Orchestrate with protocol and reasoning level
ts orchestrate "Setup CI/CD pipeline" --protocols=mcp,a2a --reasoning=high

# Discover A2A agents by keyword
ts discover a2a --words=devops,security

# Create and execute a workflow template
ts workflow create "enterprise-deploy" -u
ts workflow execute "enterprise-deploy"
```

For full command reference:

```bash
ts --help
ts q --help
ts orchestrate --help
```

## Examples

See `examples/basic_usage.sh` and `examples/advanced_workflow.yaml` for real-world scenarios.

## Testing

Run tests with `pytest`:

```bash
uv run pytest
```

## Contributing

1. Fork the repository  
2. Create a feature branch `git checkout -b feature/your-feature`  
3. Install dependencies and run tests  
4. Commit and push  
5. Open a Pull Request  

Please follow code style (`black`, `flake8`) and include tests for new features.

## License

MIT © Chrono's Cyber Chronicles
