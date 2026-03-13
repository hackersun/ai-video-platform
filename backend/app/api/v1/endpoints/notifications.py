"""
通知 API 端点
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime

from app.services.notification_service import notification_service, NotificationType, NotificationPriority

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


class NotificationResponse(BaseModel):
    """通知响应"""
    id: str
    type: str
    title: str
    message: str
    priority: str
    is_read: bool
    data: dict = {}
    action_url: Optional[str] = None
    created_at: datetime
    read_at: Optional[datetime] = None


@router.get("")
async def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """获取通知列表"""
    # TODO: 从认证获取user_id
    user_id = "current_user_id"
    
    notifications = notification_service.get_notifications(
        user_id=user_id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )
    
    return {
        "items": [
            {
                "id": n.id,
                "type": n.type.value,
                "title": n.title,
                "message": n.message,
                "priority": n.priority.value,
                "is_read": n.is_read,
                "data": n.data,
                "action_url": n.action_url,
                "created_at": n.created_at,
                "read_at": n.read_at,
            }
            for n in notifications
        ],
        "total": len(notification_service.notifications.get(user_id, [])),
        "unread_count": notification_service.get_unread_count(user_id),
    }


@router.get("/unread-count")
async def get_unread_count():
    """获取未读通知数量"""
    user_id = "current_user_id"
    count = notification_service.get_unread_count(user_id)
    return {"unread_count": count}


@router.post("/{notification_id}/read")
async def mark_as_read(notification_id: str):
    """标记通知为已读"""
    user_id = "current_user_id"
    success = notification_service.mark_as_read(user_id, notification_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="通知不存在")
    
    return {
        "success": True,
        "unread_count": notification_service.get_unread_count(user_id),
    }


@router.post("/read-all")
async def mark_all_as_read():
    """标记所有通知为已读"""
    user_id = "current_user_id"
    count = notification_service.mark_all_as_read(user_id)
    
    return {
        "success": True,
        "marked_count": count,
        "unread_count": 0,
    }


@router.delete("/{notification_id}")
async def delete_notification(notification_id: str):
    """删除通知"""
    user_id = "current_user_id"
    success = notification_service.delete_notification(user_id, notification_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="通知不存在")
    
    return {
        "success": True,
        "unread_count": notification_service.get_unread_count(user_id),
    }


@router.get("/settings")
async def get_notification_settings():
    """获取通知设置"""
    return {
        "email_notifications": True,
        "push_notifications": True,
        "in_app_notifications": True,
        "notification_types": {
            "task_complete": True,
            "invitation": True,
            "mention": True,
            "comment": True,
            "cost_alert": True,
            "system": True,
        },
    }


@router.put("/settings")
async def update_notification_settings(settings: dict):
    """更新通知设置"""
    return {"message": "设置更新成功"}


# ========== 测试接口 ==========

@router.post("/test")
async def send_test_notification(
    type: str = "system",
    title: str = "测试通知",
    message: str = "这是一条测试通知",
):
    """发送测试通知"""
    user_id = "current_user_id"
    
    notification = notification_service.send_notification(
        user_id=user_id,
        type=NotificationType(type),
        title=title,
        message=message,
        priority=NotificationPriority.NORMAL,
    )
    
    return {
        "success": True,
        "notification_id": notification.id,
    }