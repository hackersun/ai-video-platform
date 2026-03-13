"""
WebSocket 实时协作服务
"""

from typing import Dict, Set, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import json
import uuid


class MessageType(str, Enum):
    """消息类型"""
    USER_JOIN = "user_join"
    USER_LEAVE = "user_leave"
    CURSOR_MOVE = "cursor_move"
    CONTENT_UPDATE = "content_update"
    SELECTION_CHANGE = "selection_change"
    EDIT_LOCK = "edit_lock"
    EDIT_UNLOCK = "edit_unlock"
    CHAT_MESSAGE = "chat_message"
    SYNC_REQUEST = "sync_request"
    SYNC_RESPONSE = "sync_response"
    SAVE = "save"
    SAVE_ACK = "save_ack"


@dataclass
class User:
    """用户"""
    id: str
    username: str
    color: str  # 随机颜色用于区分
    cursor_position: int = 0
    selection_start: Optional[int] = None
    selection_end: Optional[int] = None
    last_active: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CollaborationRoom:
    """协作房间"""
    id: str
    resource_type: str  # novel, chapter, script, scene
    resource_id: str
    users: Dict[str, User] = field(default_factory=dict)
    lock_owner: Optional[str] = None  # 当前编辑锁持有者
    content: str = ""  # 当前内容
    version: int = 1
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class CollaborationManager:
    """协作管理器"""

    def __init__(self):
        self.rooms: Dict[str, CollaborationRoom] = {}
        self.user_rooms: Dict[str, Set[str]] = {}  # user_id -> room_ids

    def create_room(
        self,
        resource_type: str,
        resource_id: str,
        initial_content: str = ""
    ) -> str:
        """创建协作房间"""
        room_id = f"{resource_type}:{resource_id}"
        
        if room_id in self.rooms:
            return room_id
        
        self.rooms[room_id] = CollaborationRoom(
            id=room_id,
            resource_type=resource_type,
            resource_id=resource_id,
            content=initial_content,
        )
        
        return room_id

    def join_room(self, room_id: str, user: User) -> Dict:
        """用户加入房间"""
        if room_id not in self.rooms:
            self.create_room(room_id.split(":")[0], room_id.split(":")[1])
        
        room = self.rooms[room_id]
        room.users[user.id] = user
        
        # 记录用户的房间
        if user.id not in self.user_rooms:
            self.user_rooms[user.id] = set()
        self.user_rooms[user.id].add(room_id)
        
        return {
            "type": MessageType.USER_JOIN,
            "room_id": room_id,
            "user": {
                "id": user.id,
                "username": user.username,
                "color": user.color,
            },
            "users": [
                {"id": u.id, "username": u.username, "color": u.color}
                for u in room.users.values()
            ],
            "lock_owner": room.lock_owner,
            "content": room.content,
            "version": room.version,
        }

    def leave_room(self, room_id: str, user_id: str) -> Dict:
        """用户离开房间"""
        if room_id not in self.rooms:
            return {}
        
        room = self.rooms[room_id]
        
        if user_id in room.users:
            del room.users[user_id]
        
        # 移除用户的房间记录
        if user_id in self.user_rooms:
            self.user_rooms[user_id].discard(room_id)
        
        # 如果编辑锁是该用户的，释放锁
        if room.lock_owner == user_id:
            room.lock_owner = None
        
        # 如果房间空了，删除房间
        if not room.users:
            del self.rooms[room_id]
            return None
        
        return {
            "type": MessageType.USER_LEAVE,
            "room_id": room_id,
            "user_id": user_id,
            "users": [
                {"id": u.id, "username": u.username, "color": u.color}
                for u in room.users.values()
            ],
        }

    def update_cursor(
        self,
        room_id: str,
        user_id: str,
        position: int,
        selection_start: Optional[int] = None,
        selection_end: Optional[int] = None
    ) -> Dict:
        """更新光标位置"""
        if room_id not in self.rooms:
            return {}
        
        room = self.rooms[room_id]
        
        if user_id in room.users:
            user = room.users[user_id]
            user.cursor_position = position
            user.selection_start = selection_start
            user.selection_end = selection_end
            user.last_active = datetime.utcnow()
        
        return {
            "type": MessageType.CURSOR_MOVE,
            "room_id": room_id,
            "user_id": user_id,
            "position": position,
            "selection_start": selection_start,
            "selection_end": selection_end,
        }

    def request_edit_lock(
        self,
        room_id: str,
        user_id: str
    ) -> Dict:
        """请求编辑锁"""
        if room_id not in self.rooms:
            return {"success": False, "message": "房间不存在"}
        
        room = self.rooms[room_id]
        
        # 如果已经有锁且不是该用户的
        if room.lock_owner and room.lock_owner != user_id:
            return {
                "success": False,
                "message": "内容正在被其他人编辑",
                "lock_owner": room.lock_owner,
            }
        
        # 授予锁
        room.lock_owner = user_id
        
        return {
            "success": True,
            "type": MessageType.EDIT_LOCK,
            "room_id": room_id,
            "user_id": user_id,
        }

    def release_edit_lock(self, room_id: str, user_id: str) -> Dict:
        """释放编辑锁"""
        if room_id not in self.rooms:
            return {}
        
        room = self.rooms[room_id]
        
        if room.lock_owner == user_id:
            room.lock_owner = None
        
        return {
            "type": MessageType.EDIT_UNLOCK,
            "room_id": room_id,
            "user_id": user_id,
        }

    def update_content(
        self,
        room_id: str,
        user_id: str,
        content: str,
        cursor_position: int
    ) -> Dict:
        """更新内容"""
        if room_id not in self.rooms:
            return {}
        
        room = self.rooms[room_id]
        
        # 检查编辑锁
        if room.lock_owner and room.lock_owner != user_id:
            return {
                "success": False,
                "message": "内容正在被其他人编辑",
            }
        
        room.content = content
        room.version += 1
        room.updated_at = datetime.utcnow()
        
        return {
            "success": True,
            "type": MessageType.CONTENT_UPDATE,
            "room_id": room_id,
            "user_id": user_id,
            "content": content,
            "version": room.version,
            "cursor_position": cursor_position,
        }

    def get_room_info(self, room_id: str) -> Optional[Dict]:
        """获取房间信息"""
        if room_id not in self.rooms:
            return None
        
        room = self.rooms[room_id]
        
        return {
            "id": room.id,
            "resource_type": room.resource_type,
            "resource_id": room.resource_id,
            "users": [
                {
                    "id": u.id,
                    "username": u.username,
                    "color": u.color,
                    "cursor_position": u.cursor_position,
                }
                for u in room.users.values()
            ],
            "lock_owner": room.lock_owner,
            "content": room.content,
            "version": room.version,
        }

    def handle_message(self, message: Dict) -> Dict:
        """处理收到的消息"""
        msg_type = message.get("type")
        
        if msg_type == MessageType.USER_JOIN:
            return self.join_room(
                message["room_id"],
                User(
                    id=message["user"]["id"],
                    username=message["user"]["username"],
                    color=message["user"]["color"],
                )
            )
        
        elif msg_type == MessageType.USER_LEAVE:
            return self.leave_room(message["room_id"], message["user_id"])
        
        elif msg_type == MessageType.CURSOR_MOVE:
            return self.update_cursor(
                message["room_id"],
                message["user_id"],
                message.get("position", 0),
                message.get("selection_start"),
                message.get("selection_end")
            )
        
        elif msg_type == MessageType.CONTENT_UPDATE:
            return self.update_content(
                message["room_id"],
                message["user_id"],
                message.get("content", ""),
                message.get("cursor_position", 0)
            )
        
        elif msg_type == MessageType.EDIT_LOCK:
            return self.request_edit_lock(message["room_id"], message["user_id"])
        
        elif msg_type == MessageType.EDIT_UNLOCK:
            return self.release_edit_lock(message["room_id"], message["user_id"])
        
        return {}


# 全局协作管理器
collaboration_manager = CollaborationManager()


# 生成随机用户颜色
def generate_user_color() -> str:
    """生成随机用户颜色"""
    colors = [
        "#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A",
        "#98D8C8", "#F7DC6F", "#BB8FCE", "#85C1E2",
    ]
    return colors[uuid.uuid4().int % len(colors)]