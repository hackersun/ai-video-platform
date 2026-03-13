"""
WebSocket 实时协作端点
"""

from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
import json
import uuid

from app.services.collaboration_service import (
    collaboration_manager,
    User,
    generate_user_color,
)

router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/collaborate/{room_id}")
async def collaboration_websocket(
    websocket: WebSocket,
    room_id: str,
    token: str = Query(...),
):
    """WebSocket 协作连接"""
    await websocket.accept()
    
    # TODO: 验证token获取用户信息
    user_id = f"user_{uuid.uuid4().hex[:8]}"
    username = f"用户{uuid.uuid4().hex[:4]}"
    
    # 创建用户
    user = User(
        id=user_id,
        username=username,
        color=generate_user_color(),
    )
    
    # 加入房间
    join_message = collaboration_manager.join_room(room_id, user)
    
    # 广播用户加入
    await websocket.send_json({
        "type": "connected",
        "user_id": user_id,
        "room_info": collaboration_manager.get_room_info(room_id),
    })
    
    try:
        while True:
            # 接收消息
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # 添加用户ID
            message["user_id"] = user_id
            message["room_id"] = room_id
            
            # 处理消息
            response = collaboration_manager.handle_message(message)
            
            # 发送响应
            if response:
                await websocket.send_json(response)
                
                # 广播给其他用户
                # TODO: 实现广播机制
                
    except WebSocketDisconnect:
        # 用户断开连接
        leave_message = collaboration_manager.leave_room(room_id, user_id)
        if leave_message:
            # 广播用户离开
            pass
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": str(e),
        })
    finally:
        await websocket.close()


@router.get("/rooms/{room_id}/info")
async def get_room_info(room_id: str):
    """获取房间信息"""
    info = collaboration_manager.get_room_info(room_id)
    if not info:
        return {"error": "Room not found"}
    return info


@router.get("/rooms/{room_id}/users")
async def get_room_users(room_id: str):
    """获取房间用户列表"""
    info = collaboration_manager.get_room_info(room_id)
    if not info:
        return {"users": []}
    return {"users": info["users"]}