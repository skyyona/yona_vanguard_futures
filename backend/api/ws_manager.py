from typing import List, Dict, Any
from starlette.websockets import WebSocket
import json

class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_text(self, message: str):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)
        
        # 연결이 끊어진 소켓 제거
        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast_json(self, data: Dict[str, Any]):
        message = json.dumps(data, ensure_ascii=False)
        await self.broadcast_text(message)

# 싱글턴 인스턴스
ws_manager = WebSocketManager()