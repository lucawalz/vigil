import asyncio
import shutil
import stat
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from vigil_lab.hub import FRAME_HEADER_BYTES, SOCKET_MODE, Hub, serve

ETHERNET_MTU = 1500
FRAME = b"x" * ETHERNET_MTU
FLOOD_FRAMES = 4000
TEST_BUFFER_LIMIT = 64 * 1024
SENTINEL = b"sentinel"
SENTINEL_RETRY_S = 0.05
RECEIVE_TIMEOUT_S = 10
TRUNCATED_LENGTH = 100
CLIENT_COUNT = 3
POLL_S = 0.01
SOCKET_SETTLE_S = 0.05


def _packet(payload: bytes) -> bytes:
    return len(payload).to_bytes(FRAME_HEADER_BYTES, "big") + payload


@pytest.fixture
def socket_path() -> Iterator[Path]:
    directory = Path(tempfile.mkdtemp(prefix="vl", dir="/tmp"))
    yield directory / "hub.sock"
    shutil.rmtree(directory, ignore_errors=True)


async def _wait_for_clients(hub: Hub, count: int) -> None:
    while len(hub.clients) < count:
        await asyncio.sleep(POLL_S)


async def _wait_for_clients_below(hub: Hub, count: int) -> None:
    while len(hub.clients) >= count:
        await asyncio.sleep(POLL_S)


async def _until_sentinel(reader: asyncio.StreamReader) -> None:
    while True:
        header = await reader.readexactly(FRAME_HEADER_BYTES)
        if await reader.readexactly(int.from_bytes(header, "big")) == SENTINEL:
            return


async def _send_sentinels(writer: asyncio.StreamWriter) -> None:
    while True:
        writer.write(_packet(SENTINEL))
        await writer.drain()
        await asyncio.sleep(SENTINEL_RETRY_S)


async def test_hub_keeps_relaying_while_a_client_stalls(socket_path: Path) -> None:
    hub = Hub(write_buffer_limit=TEST_BUFFER_LIMIT)
    server = await asyncio.start_unix_server(hub.relay, path=str(socket_path))
    async with server:
        _, stalled = await asyncio.open_unix_connection(str(socket_path))
        live_reader, live = await asyncio.open_unix_connection(str(socket_path))
        _, sender = await asyncio.open_unix_connection(str(socket_path))
        await _wait_for_clients(hub, CLIENT_COUNT)
        for _ in range(FLOOD_FRAMES):
            sender.write(_packet(FRAME))
            await sender.drain()
            await asyncio.sleep(0)
        sentinels = asyncio.create_task(_send_sentinels(sender))
        await asyncio.wait_for(_until_sentinel(live_reader), RECEIVE_TIMEOUT_S)
        sentinels.cancel()
        assert hub.dropped_frames > 0
        bound = TEST_BUFFER_LIMIT + len(_packet(FRAME))
        assert all(w.transport.get_write_buffer_size() <= bound for w in hub.clients)
        for writer in (stalled, live, sender):
            writer.close()


async def test_hub_survives_a_client_closing_mid_frame(socket_path: Path) -> None:
    hub = Hub()
    server = await asyncio.start_unix_server(hub.relay, path=str(socket_path))
    async with server:
        _, broken = await asyncio.open_unix_connection(str(socket_path))
        reader, receiver = await asyncio.open_unix_connection(str(socket_path))
        _, sender = await asyncio.open_unix_connection(str(socket_path))
        await _wait_for_clients(hub, CLIENT_COUNT)
        broken.write(TRUNCATED_LENGTH.to_bytes(FRAME_HEADER_BYTES, "big") + b"short")
        await broken.drain()
        broken.close()
        await _wait_for_clients_below(hub, CLIENT_COUNT)
        sender.write(_packet(SENTINEL))
        await sender.drain()
        await asyncio.wait_for(_until_sentinel(reader), RECEIVE_TIMEOUT_S)
        for writer in (receiver, sender):
            writer.close()


async def test_serve_restricts_the_socket_to_the_owner(socket_path: Path) -> None:
    task = asyncio.create_task(serve(socket_path))
    while not socket_path.exists():
        await asyncio.sleep(POLL_S)
    await asyncio.sleep(SOCKET_SETTLE_S)
    assert stat.S_IMODE(socket_path.stat().st_mode) == SOCKET_MODE
    task.cancel()
