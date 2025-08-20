# Orchestrator Taskflow Plan (Human-readable)

This document mirrors our active planning for the orchestrator MCP aggregator port and related work. It acts as a durable backup of completed and upcoming tasks.

Legend:
- [x] done
- [ ] pending
- [>] in progress

## Phase 1: MCP Aggregator Port (Priority 1)

- [x] Repo/tooling setup (pyproject, ruff, pytest, pre-commit, Makefile)
- [x] Package scaffold (src/orchestrator, tests)
- [x] Stdout hygiene utilities
- [x] Stdio transport framer (Content-Length)
- [x] Minimal MCP stdio loop with initialize
- [x] Upstream process manager
- [x] CLI wiring with --config and graceful shutdown
- [x] UpstreamClient for stdio JSON-RPC
- [x] Aggregate initialize across upstreams (capabilities union)
- [ ] Routing scaffold (forward non-initialize requests)
- [ ] Discovery parity (tools/resources/prompts), include/exclude filters
- [ ] Robust error handling and logging structure
- [ ] Cursor/Claude Desktop compatibility validation

## Phase 2: Integration/Config (Priority 2)

- [ ] Config parity with combine-mcp (YAML/JSON), env/CLI precedence
- [ ] CLI commands for validation and dry-run
- [ ] Documentation for setup and client integration

## Phase 3: Additional Transports (Priority 3)

- [ ] HTTP+SSE transport
- [ ] WebSocket transport

## Phase 4: A2A and Bridging (Priority 4)

- [ ] A2A client/server drivers
- [ ] MCP  A2A bridging flows

## Tests & CI

- [x] Unit test scaffold
- [ ] Integration tests for upstream discovery/aggregation
- [ ] E2E with selected MCP clients

## Notes
- Maintain absolute imports preference
- Maintain strict stdout hygiene for stdio
- Keep docs in docs/; align with alignment.md
