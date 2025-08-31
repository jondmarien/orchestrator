from __future__ import annotations

import asyncio
import logging

import typer

from orchestrator.mcp.aggregator import MCPAggregatorServer

app = typer.Typer(add_completion=False)


async def _run_stdio(name: str | None, config_path: str | None) -> None:
    server_name = name or "orchestrator-mcp-aggregator"

    # Optionally load config and start upstream servers
    upstream_manager = None
    controller = None
    cfg = None
    if config_path:
        from orchestrator.config_loader import load_config
        from orchestrator.mcp.aggregator.controller import AggregationController
        from orchestrator.mcp.aggregator.upstream import UpstreamProcessManager

        cfg = load_config(config_path)
        upstream_manager = UpstreamProcessManager()

    try:
        # Prefer SDK-backed path: construct controller with configs (no local process launch)
        use_sdk = False
        try:
            import importlib

            importlib.import_module("mcp.client.stdio")
            use_sdk = True
        except Exception:
            use_sdk = False

        if cfg and cfg.upstream:
            if use_sdk:
                controller = AggregationController(upstream_servers=cfg.upstream)
            else:
                # Fall back to local subprocess launch + lightweight client
                if upstream_manager is None:
                    from orchestrator.mcp.aggregator.upstream import UpstreamProcessManager

                    upstream_manager = UpstreamProcessManager()
                ups = await upstream_manager.start_all(cfg.upstream)
                controller = AggregationController(upstream_processes=ups)
        server = MCPAggregatorServer(
            name=server_name, initial_capabilities=None, controller=controller
        )
        async with server:
            await server.start_stdio()
    finally:
        # Close controller first to stop client reader tasks
        if controller is not None:
            await controller.aclose()
        if upstream_manager:
            await upstream_manager.stop_all()


@app.callback(invoke_without_command=True)
def default(
    ctx: typer.Context,
    name: str | None = typer.Option(None, help="Server name for diagnostics"),
    config: str | None = typer.Option(None, "--config", "-c", help="Path to YAML/JSON config"),
    client_profile: str | None = typer.Option(
        None, "--client-profile", help="Client profile: cursor|windsurf (overrides config/env)"
    ),
) -> None:
    """Run the MCP aggregator over stdio (for MCP clients like Cursor)."""
    if ctx.invoked_subcommand is None:
        try:
            import os

            if client_profile:
                os.environ["ORCH_CLIENT_PROFILE"] = client_profile
            asyncio.run(_run_stdio(name, config))
        except KeyboardInterrupt:
            logging.getLogger(__name__).info("Received KeyboardInterrupt, shutting down.")


@app.command("stdio")
def stdio(
    name: str | None = typer.Option(None, help="Server name for diagnostics"),
    config: str | None = typer.Option(None, "--config", "-c", help="Path to YAML/JSON config"),
    client_profile: str | None = typer.Option(
        None, "--client-profile", help="Client profile: cursor|windsurf (overrides config/env)"
    ),
) -> None:
    """Run the MCP aggregator over stdio (for MCP clients like Cursor)."""
    try:
        # Respect CLI overrides for client profile by setting env var for this process
        import os

        if client_profile:
            os.environ["ORCH_CLIENT_PROFILE"] = client_profile
        asyncio.run(_run_stdio(name, config))
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Received KeyboardInterrupt, shutting down.")


@app.command("http-sse")
def http_sse(
    host: str = typer.Option("127.0.0.1", help="Bind host"),
    port: int = typer.Option(7332, help="Bind port"),
    config: str | None = typer.Option(None, "--config", "-c", help="Path to YAML/JSON config"),
) -> None:
    """Run the MCP aggregator over HTTP/SSE (ASGI)."""
    try:
        import asyncio

        from orchestrator.mcp.aggregator.controller import AggregationController
        from orchestrator.mcp.aggregator.upstream import UpstreamProcessManager
        from orchestrator.transport.http_sse import HttpSseTransport

        controller = None
        cfg = None
        upstream_manager = None
        if config:
            from orchestrator.config_loader import load_config

            cfg = load_config(config)

        async def _run() -> None:
            nonlocal controller, upstream_manager
            use_sdk = False
            try:
                import importlib

                importlib.import_module("mcp.client.stdio")
                use_sdk = True
            except Exception:
                use_sdk = False

            if cfg and cfg.upstream:
                if use_sdk:
                    controller = AggregationController(upstream_servers=cfg.upstream)
                else:
                    upstream_manager = UpstreamProcessManager()
                    ups = await upstream_manager.start_all(cfg.upstream)
                    controller = AggregationController(upstream_processes=ups)
            else:
                controller = AggregationController([])

            # Warm up and log upstream initialization status
            try:
                caps = await controller.initialize_capabilities()
                logging.getLogger(__name__).info(
                    "Initialized upstreams via HTTP/SSE: tools=%d prompts=%d resources=%d",
                    len(caps.get("tools", {})),
                    len(caps.get("prompts", {})),
                    len(caps.get("resources", {})),
                )
            except Exception as e:
                logging.getLogger(__name__).warning("Initialization warmup failed: %s", e)

            transport = HttpSseTransport()
            await transport.run(controller, host=host, port=port)

        asyncio.run(_run())
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Received KeyboardInterrupt, shutting down.")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
