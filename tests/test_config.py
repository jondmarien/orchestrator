from orchestrator.config import AggregatorConfig, TransportConfig, UpstreamServer


def test_config_defaults():
    cfg = AggregatorConfig()
    assert cfg.name == "orchestrator-mcp-aggregator"
    assert cfg.transport.mode == "stdio"
    assert cfg.strict_stdout is True


def test_config_customization():
    cfg = AggregatorConfig(
        name="custom",
        transport=TransportConfig(mode="http-sse", host="0.0.0.0", port=9000),
        upstream=[
            UpstreamServer(name="s1", command=["server-a", "--flag"], env={"FOO": "bar"}),
            UpstreamServer(name="s2", command=["server-b"]),
        ],
    )
    assert cfg.name == "custom"
    assert cfg.transport.mode == "http-sse"
    assert len(cfg.upstream) == 2
