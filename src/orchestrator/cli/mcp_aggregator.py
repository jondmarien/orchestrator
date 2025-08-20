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
        if upstream_manager and cfg and cfg.upstream:
            ups = await upstream_manager.start_all(cfg.upstream)
            controller = AggregationController(ups)
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
) -> None:
    """Run the MCP aggregator over stdio (for MCP clients like Cursor)."""
    if ctx.invoked_subcommand is None:
        try:
            asyncio.run(_run_stdio(name, config))
        except KeyboardInterrupt:
            logging.getLogger(__name__).info("Received KeyboardInterrupt, shutting down.")


@app.command("stdio")
def stdio(
    name: str | None = typer.Option(None, help="Server name for diagnostics"),
    config: str | None = typer.Option(None, "--config", "-c", help="Path to YAML/JSON config"),
) -> None:
    """Run the MCP aggregator over stdio (for MCP clients like Cursor)."""
    try:
        asyncio.run(_run_stdio(name, config))
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Received KeyboardInterrupt, shutting down.")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
