# Orchestrator Implementation Alignment

## Project Scope Alignment

### ✅ Aligned Items

1. **Python Port of combine-mcp**: Plan confirms porting Go MCP aggregator to Python
2. **Dual Protocol Support**: MCP + A2A protocols with clear separation of concerns
   - MCP: Agent-to-Tool interactions (stateless, transactional)
   - A2A: Agent-to-Agent collaboration (stateful, conversational)
3. **GPT-OSS Integration**: Via Hugging Face Inference API
4. **CLI with `ts` alias**: Typer-based CLI with mode flags
5. **uv Environment Management**: Full adoption of uv for dependency management
6. **Configuration**: Pydantic models with YAML/JSON support
7. **Testing Strategy**: pytest with unit/integration/e2e tests
8. **Shared Transport Layer**: Reusable JSON-RPC 2.0, SSE, and HTTP implementations for both protocols

### 🔄 Adjustments Needed

#### 1. **Multi-Client & Transport Support (NEW)**

- **Plan**: Focused primarily on Cursor compatibility
- **Our Approach**: Support ALL major MCP clients and transports:
  - **Clients to Support**:
    - Claude Desktop App (Resources, Prompts, Tools)
    - Cursor (Tools only, 2-server limit workaround)
    - Continue (Resources, Prompts, Tools)
    - Cline (Resources, Tools, Discovery)
    - Windsurf Editor (Full support)
    - Zed (Tools)
    - VS Code GitHub Copilot (Tools)
    - JetBrains AI Assistant (Tools)
    - LM Studio (Tools)
    - And 60+ other clients
  - **Transports**:
    - stdio (primary - subprocess communication)
    - Streamable HTTP with SSE (for web-based clients)
    - WebSocket support (future)
  - **Protocol Versions**:
    - Current: 2025-06-18
    - Legacy: 2024-11-05 (HTTP+SSE)
    - Version negotiation during initialization
- **Rationale**: Maximum ecosystem compatibility, future-proof

#### 2. **Package Structure**

- **Plan**: Places everything under single `orchestrator/` directory
- **Our Approach**: Use `src/orchestrator/` layout with sub-packages:

  ```sh
  src/
  └── orchestrator/
      ├── mcp/
      │   └── aggregator/  # MCP aggregator specific code
      ├── protocols/        # Protocol drivers
      ├── cli/             # CLI commands
      └── core/            # Core orchestration logic
  ```

- **Rationale**: Better separation of concerns, easier to maintain MCP aggregator as distinct module

#### 3. **MCP Implementation Details**

- **Plan**: Basic MCP driver in `drivers/mcp.py`
- **Our Approach**: Full aggregator implementation matching combine-mcp:
  - Dedicated `mcp/aggregator/` package
  - Stdio server for Cursor compatibility
  - Tool filtering and sanitization logic
  - Standalone entry point `orchestrator-mcp-aggregator`
- **Rationale**: Maintain full combine-mcp compatibility for migration path

#### 4. **Stdout Hygiene**

- **Plan**: Not explicitly addressed
- **Our Approach**: Critical requirement for MCP/Cursor compatibility:
  - StdoutGuard context manager
  - All logs to stderr/file only
  - Clean JSON-RPC on stdout
- **Rationale**: Essential for Cursor integration

#### 5. **A2A Protocol Integration (NEW)**

- **Plan**: Basic A2A driver mentioned
- **Our Approach**: Full A2A implementation as Google's agent collaboration standard:
  - **A2A Client**: Agent discovery via Agent Cards, task management, multi-transport
  - **A2A Server**: Expose orchestrator as A2A-compliant agent
  - **Protocol Bridging**: Seamless MCP ↔ A2A interoperability
  - **Transports**: JSON-RPC 2.0, gRPC, REST/HTTP+JSON
  - **Task Management**: Stateful, long-running operations with persistence
  - **Authentication**: OAuth2, API keys, mTLS support
- **Rationale**: Enable true multi-agent collaboration, not just tool usage

#### 6. **Development Timeline**

- **Plan**: 18-week timeline with 4 phases
- **Our Approach**: Phased delivery with faster iteration:
  - **Weeks 1-2**: MCP aggregator port and testing
  - **Weeks 3-4**: A2A client implementation
  - **Weeks 5-6**: A2A server and protocol bridging
  - **Month 2+**: Advanced features and optimization
- **Rationale**: Faster iteration, early validation, progressive enhancement

## Protocol Architecture

### MCP vs A2A: Complementary Roles

```
┌─────────────────────────────────────────────────────┐
│                  User/Application                    │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│                   Orchestrator                       │
│  ┌─────────────────────────────────────────────┐   │
│  │           Protocol Abstraction Layer         │   │
│  ├──────────────────┬───────────────────────────┤   │
│  │   MCP Driver     │      A2A Driver           │   │
│  ├──────────────────┼───────────────────────────┤   │
│  │ • Tool access    │ • Agent discovery         │   │
│  │ • Resources      │ • Task management         │   │
│  │ • Prompts        │ • Multi-turn conversation │   │
│  │ • Stateless ops  │ • Stateful collaboration  │   │
│  └──────────────────┴───────────────────────────┘   │
└─────────────────────────────────────────────────────┘
           │                          │
           ▼                          ▼
    ┌──────────────┐          ┌──────────────┐
    │  MCP Servers │          │  A2A Agents  │
    │  (Tools)     │          │  (Peers)     │
    └──────────────┘          └──────────────┘
```

### Transport Layer Sharing

Both protocols can share transport implementations:
- **JSON-RPC 2.0**: Primary for both MCP and A2A
- **SSE Streaming**: Real-time updates for both
- **HTTP/REST**: Alternative transport
- **gRPC**: A2A-specific (future MCP support possible)

## Implementation Priorities

### Phase 1: MCP Aggregator (Priority 1)

1. Port combine-mcp to Python
2. Ensure Cursor compatibility
3. Support existing config formats
4. Comprehensive testing

### Phase 2: Integration (Priority 2)

1. Protocol driver abstraction
2. CLI commands for MCP
3. Configuration management
4. Documentation

### Phase 3: A2A & Orchestration (Priority 3)

1. A2A driver implementation
2. QueryAnalyzer with GPT-OSS
3. Workflow engine
4. Advanced features

## Key Technical Decisions

### ✅ Confirmed from Plan

- AsyncIO for all I/O operations
- Pydantic for configuration and validation
- Typer for CLI framework
- pytest for testing
- GitHub Actions for CI/CD

### 📝 Additional Decisions

- **JSON-RPC**: Implement minimal helpers for MCP protocol
- **Tool Filtering**: Exact parity with combine-mcp logic
- **Config Precedence**: ENV > CLI > JSON > YAML
- **Logging**: Structured logging with correlation IDs
- **Entry Points**: Both `ts` and `orchestrator-mcp-aggregator`
- **Transport Factory**: Pluggable transport selection based on config
- **Client Detection**: Auto-detect client type from initialization
- **Feature Negotiation**: Support partial MCP features per client

## Resource Allocation

### Development Environment

- Python 3.11+ (per plan)
- Windows + Linux compatibility (our requirement)
- Docker support (per plan)

### HF/GPT-OSS Credits

- Plan allocates $50 total
- Defer GPT-OSS integration to Phase 3
- Focus initial work on MCP aggregator (no AI needed)

## Success Criteria

### Immediate (Week 1)

- [ ] MCP aggregator runs with Cursor
- [ ] Multiple backend servers initialize
- [ ] Tool filtering works
- [ ] No stdout pollution

### Short-term (Week 2-3)

- [ ] Full combine-mcp feature parity
- [ ] CI/CD pipeline active
- [ ] Documentation complete
- [ ] Migration guide available

### Long-term (Month 1-3)

- [ ] A2A protocol integrated
- [ ] GPT-OSS reasoning active
- [ ] Workflow engine operational
- [ ] Community adoption metrics met

## Next Steps

1. **Continue with Task #2**: Review complete, proceeding with implementation
2. **Create package structure** as outlined above
3. **Set up development tooling** (uv, ruff, pytest)
4. **Begin MCP aggregator port** focusing on Cursor compatibility

## Questions for Confirmation

None - the plan aligns well with our vision. The adjustments noted above enhance rather than contradict the original plan, focusing on:

- Better code organization
- Faster MVP delivery
- Maintaining combine-mcp compatibility
- Ensuring Cursor integration works perfectly
