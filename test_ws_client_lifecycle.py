import time
import asyncio
import json
from PySide6.QtWidgets import QApplication

from utils.ws_client import WebSocketClient


class _FakeWS:
    def __init__(self):
        self.closed = False

    async def recv(self):
        # return one message then sleep long so loop stays alive briefly
        await asyncio.sleep(0.05)
        return json.dumps({"type": "HEARTBEAT"})

    async def close(self):
        self.closed = True


class _FakeConnectCtx:
    def __init__(self, uri):
        self._ws = _FakeWS()

    async def __aenter__(self):
        return self._ws

    async def __aexit__(self, exc_type, exc, tb):
        try:
            await self._ws.close()
        except Exception:
            pass


def fake_connect(uri):
    return _FakeConnectCtx(uri)


def test_wsclient_start_stop(monkeypatch):
    """Start the threaded WebSocketClient and stop it; ensure thread exits cleanly."""
    # Ensure a Qt application exists so Signal emission is safe
    app = QApplication.instance() or QApplication([])

    # Patch websockets.connect used by WebSocketClient
    monkeypatch.setattr("websockets.connect", fake_connect)

    client = WebSocketClient("ws://localhost:9999/ws")
    client.start()

    # allow some time for thread and its loop to start and perform a recv
    time.sleep(0.2)

    assert client.isRunning(), "WebSocketClient thread did not start"

    # Stop and wait briefly for it to shut down
    client.stop()
    time.sleep(0.2)

    assert not client.isRunning(), "WebSocketClient thread did not stop"
