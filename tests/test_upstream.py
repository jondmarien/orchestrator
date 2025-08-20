from unittest.mock import AsyncMock, patch

import pytest

from orchestrator.config import UpstreamServer
from orchestrator.mcp.aggregator.upstream import UpstreamProcessManager


@pytest.mark.asyncio
async def test_start_one_process_mocked():
    mngr = UpstreamProcessManager()
    cfg = UpstreamServer(name="s1", command=["dummy-server"])

    mock_proc = AsyncMock()
    mock_proc.returncode = None

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        up = await mngr.start_one(cfg)
        assert up.name == "s1"
        assert up.is_running()


@pytest.mark.asyncio
async def test_stop_all_processes_mocked():
    mngr = UpstreamProcessManager()
    cfg = UpstreamServer(name="s1", command=["dummy-server"])

    mock_proc = AsyncMock()
    mock_proc.returncode = None
    mock_proc.wait = AsyncMock()

    # terminate/kill are sync on real Process; make them regular Mocks to avoid warnings
    from unittest.mock import Mock

    mock_proc.terminate = Mock()
    mock_proc.kill = Mock()

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        await mngr.start_one(cfg)
        await mngr.stop_all()
        mock_proc.terminate.assert_called_once()
