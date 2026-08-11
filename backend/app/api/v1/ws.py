"""Real-time AI activity over WebSocket.

A worker/API process publishes events to Redis channel `agent:{workspace_id}`;
ANY connected client for that workspace receives them live. Auth is a Clerk JWT
posted as the first message (`{"token": "..."}`) right after connect.

This is grounded in real backend events (see agent_realtime.publish_activity) —
there are no fake/curated events."""

import json

import redis.asyncio as redis_async
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.core.security import verify_clerk_jwt

router = APIRouter(prefix="/agent", tags=["agent-ws"])


@router.websocket("/ws")
async def agent_events_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    workspace_id = None
    sub = None
    try:
        auth = await websocket.receive_json()
        token = (auth or {}).get("token") or ""
        if not token:
            await websocket.send_json({"type": "error", "detail": "missing token"})
            await websocket.close(code=4401)
            return
        claims = verify_clerk_jwt(token)
        user_id = claims["sub"]

        from app.db.session import async_session_maker
        from app.services.workspace_service import get_workspace_for_user

        async with async_session_maker() as session:
            workspace = await get_workspace_for_user(session, user_id)
            if workspace is None:
                await websocket.send_json({"type": "error", "detail": "no workspace"})
                await websocket.close(code=4403)
                return
            workspace_id = workspace.id

        cache = redis_async.from_url(settings.redis_url, decode_responses=True)
        sub = cache.pubsub()
        await sub.subscribe(f"agent:{workspace_id}")
        await websocket.send_json({"type": "connected", "workspace_id": workspace_id})

        while True:
            message = await sub.get_message(ignore_subscribe_messages=True, timeout=15.0)
            if message and message.get("type") == "message":
                try:
                    await websocket.send_text(message["data"])
                except Exception:
                    break
            else:
                # Periodic keepalive so a proxy doesn't drop the connection.
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        if sub is not None:
            try:
                await sub.unsubscribe()
            except Exception:
                pass