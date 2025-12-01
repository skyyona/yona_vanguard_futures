import asyncio
import websockets
import json
from PySide6.QtCore import QThread, Signal


class WebSocketClient(QThread):
    message_received = Signal(dict)

    def __init__(self, uri):
        super().__init__()
        self.uri = uri
        self._is_running = True
        self._loop = None

    def run(self):
        # Create and run a dedicated event loop for this thread so we can stop it cleanly
        loop = asyncio.new_event_loop()
        self._loop = loop
        try:
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._connect_async())
            except RuntimeError:
                # loop.stop() may cause run_until_complete to raise; ignore during shutdown
                pass
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()
            self._loop = None

    async def _connect_async(self):
        while self._is_running:
            try:
                async with websockets.connect(self.uri) as websocket:
                    print(f"WebSocket에 연결되었습니다: {self.uri}")
                    while self._is_running:
                        try:
                            message = await websocket.recv()
                            data = json.loads(message)
                            self.message_received.emit(data)
                        except websockets.ConnectionClosed:
                            print("WebSocket 연결이 닫혔습니다. 재연결 시도 중...")
                            break
                        except json.JSONDecodeError:
                            print(f"잘못된 JSON 형식의 메시지 수신: {message}")
                        except Exception as e:
                            print(f"메시지 처리 중 오류 발생: {e}")
                            break
            except Exception as e:
                if not self._is_running:
                    break
                print(f"WebSocket 연결 실패: {e}. 5초 후 재시도합니다.")
                try:
                    await asyncio.sleep(5)
                except asyncio.CancelledError:
                    break

    def stop(self):
        # signal the coroutine to stop and stop the loop safely
        self._is_running = False
        if self._loop is not None:
            try:
                self._loop.call_soon_threadsafe(self._loop.stop)
            except Exception:
                pass
        self.quit()
        # wait for thread to finish; block for a short time
        try:
            self.wait(3000)
        except Exception:
            pass