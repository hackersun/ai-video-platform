"""
通知服务
"""

from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum
import uuid


class NotificationType(str, Enum):
    """通知类型"""
    SYSTEM = "system"           # 系统通知
    TASK_COMPLETE = "task_complete"  # 任务完成
    INVITATION = "invitation"   # 邀请
    COMMENT = "comment"         # 评论
    MENTION = "mention"         # 提及
    SHARE = "share"             # 分享
    EXPORT_COMPLETE = "export_complete"  # 导出完成
    COST_ALERT = "cost_alert"   # 成本告警
    SECURITY = "security"       # 安全通知


class NotificationPriority(str, Enum):
    """通知优先级"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class Notification:
    """通知"""
    
    def __init__(
        self,
        user_id: str,
        type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        data: Dict = None,
        action_url: str = None,
    ):
        self.id = str(uuid.uuid4())
        self.user_id = user_id
        self.type = type
        self.title = title
        self.message = message
        self.priority = priority
        self.data = data or {}
        self.action_url = action_url
        self.is_read = False
        self.created_at = datetime.utcnow()
        self.read_at = None


class NotificationService:
    """通知服务"""

    def __init__(self):
        self.notifications: Dict[str, List[Notification]] = {}  # user_id -> notifications
        self.unread_count: Dict[str, int] = {}  # user_id -> count

    def send_notification(
        self,
        user_id: str,
        type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        data: Dict = None,
        action_url: str = None,
    ) -> Notification:
        """发送通知"""
        notification = Notification(
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            priority=priority,
            data=data,
            action_url=action_url,
        )
        
        if user_id not in self.notifications:
            self.notifications[user_id] = []
            self.unread_count[user_id] = 0
        
        self.notifications[user_id].append(notification)
        
        if not notification.is_read:
            self.unread_count[user_id] = self.unread_count.get(user_id, 0) + 1
        
        # TODO: 推送到前端（WebSocket）
        # TODO: 发送邮件/短信（根据用户设置）
        
        return notification

    def get_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Notification]:
        """获取用户通知"""
        user_notifications = self.notifications.get(user_id, [])
        
        if unread_only:
            user_notifications = [n for n in user_notifications if not n.is_read]
        
        # 按时间倒序
        user_notifications = sorted(user_notifications, key=lambda n: n.created_at, reverse=True)
        
        return user_notifications[offset:offset + limit]

    def mark_as_read(self, user_id: str, notification_id: str) -> bool:
        """标记通知为已读"""
        user_notifications = self.notifications.get(user_id, [])
        
        for notification in user_notifications:
            if notification.id == notification_id and not notification.is_read:
                notification.is_read = True
                notification.read_at = datetime.utcnow()
                self.unread_count[user_id] = max(0, self.unread_count.get(user_id, 0) - 1)
                return True
        
        return False

    def mark_all_as_read(self, user_id: str) -> int:
        """标记所有通知为已读"""
        user_notifications = self.notifications.get(user_id, [])
        count = 0
        
        for notification in user_notifications:
            if not notification.is_read:
                notification.is_read = True
                notification.read_at = datetime.utcnow()
                count += 1
        
        self.unread_count[user_id] = 0
        return count

    def get_unread_count(self, user_id: str) -> int:
        """获取未读通知数量"""
        return self.unread_count.get(user_id, 0)

    def delete_notification(self, user_id: str, notification_id: str) -> bool:
        """删除通知"""
        user_notifications = self.notifications.get(user_id, [])
        
        for i, notification in enumerate(user_notifications):
            if notification.id == notification_id:
                if not notification.is_read:
                    self.unread_count[user_id] = max(0, self.unread_count.get(user_id, 0) - 1)
                user_notifications.pop(i)
                return True
        
        return False

    # 便捷方法
    def notify_task_complete(
        self,
        user_id: str,
        task_name: str,
        result_url: str = None,
    ) -> Notification:
        """通知任务完成"""
        return self.send_notification(
            user_id=user_id,
            type=NotificationType.TASK_COMPLETE,
            title="任务完成",
            message=f"您的任务「{task_name}」已完成",
            priority=NotificationPriority.NORMAL,
            action_url=result_url,
        )

    def notify_export_complete(
        self,
        user_id: str,
        file_name: str,
        download_url: str,
    ) -> Notification:
        """通知导出完成"""
        return self.send_notification(
            user_id=user_id,
            type=NotificationType.EXPORT_COMPLETE,
            title="导出完成",
            message=f"文件「{file_name}」已导出完成",
            priority=NotificationPriority.NORMAL,
            action_url=download_url,
        )

    def notify_invitation(
        self,
        user_id: str,
        inviter_name: str,
        team_name: str,
        invitation_url: str,
    ) -> Notification:
        """通知邀请"""
        return self.send_notification(
            user_id=user_id,
            type=NotificationType.INVITATION,
            title="团队邀请",
            message=f"{inviter_name} 邀请您加入团队「{team_name}」",
            priority=NotificationPriority.HIGH,
            action_url=invitation_url,
        )

    def notify_cost_alert(
        self,
        user_id: str,
        current_cost: float,
        budget: float,
    ) -> Notification:
        """通知成本告警"""
        percentage = (current_cost / budget) * 100 if budget > 0 else 0
        return self.send_notification(
            user_id=user_id,
            type=NotificationType.COST_ALERT,
            title="成本告警",
            message=f"今日API成本已达 ¥{current_cost:.2f}，占预算的 {percentage:.1f}%",
            priority=NotificationPriority.HIGH if percentage > 90 else NotificationPriority.NORMAL,
        )

    def notify_mention(
        self,
        user_id: str,
        mentioner_name: str,
        content: str,
        content_url: str,
    ) -> Notification:
        """通知提及"""
        return self.send_notification(
            user_id=user_id,
            type=NotificationType.MENTION,
            title="有人提及了您",
            message=f"{mentioner_name} 在「{content}」中提及了您",
            priority=NotificationPriority.NORMAL,
            action_url=content_url,
        )


# 全局通知服务实例
notification_service = NotificationService()