"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { 
  Bell, 
  Check, 
  Trash2, 
  Settings,
  CheckCircle,
  AlertCircle,
  Info,
  X
} from "lucide-react";
import { api } from "@/lib/api";
import { formatDistanceToNow } from "date-fns";
import { zhCN } from "date-fns/locale";

interface Notification {
  id: string;
  type: string;
  title: string;
  message: string;
  priority: string;
  is_read: boolean;
  data: any;
  action_url: string | null;
  created_at: string;
}

export function NotificationBell() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadNotifications();
    loadUnreadCount();
    
    // 定时刷新
    const interval = setInterval(() => {
      loadUnreadCount();
    }, 30000);
    
    return () => clearInterval(interval);
  }, []);

  const loadNotifications = async () => {
    setLoading(true);
    try {
      const response = await api.get("/api/v1/notifications?limit=20");
      setNotifications(response.data.items || []);
      setUnreadCount(response.data.unread_count || 0);
    } catch (error) {
      console.error("加载通知失败:", error);
    } finally {
      setLoading(false);
    }
  };

  const loadUnreadCount = async () => {
    try {
      const response = await api.get("/api/v1/notifications/unread-count");
      setUnreadCount(response.data.unread_count || 0);
    } catch (error) {
      console.error("加载未读数量失败:", error);
    }
  };

  const markAsRead = async (id: string) => {
    try {
      await api.post(`/api/v1/notifications/${id}/read`);
      setNotifications(prev => 
        prev.map(n => n.id === id ? { ...n, is_read: true } : n)
      );
      setUnreadCount(prev => Math.max(0, prev - 1));
    } catch (error) {
      console.error("标记已读失败:", error);
    }
  };

  const markAllAsRead = async () => {
    try {
      await api.post("/api/v1/notifications/read-all");
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch (error) {
      console.error("标记全部已读失败:", error);
    }
  };

  const deleteNotification = async (id: string) => {
    try {
      await api.delete(`/api/v1/notifications/${id}`);
      setNotifications(prev => prev.filter(n => n.id !== id));
    } catch (error) {
      console.error("删除通知失败:", error);
    }
  };

  const getIcon = (type: string) => {
    switch (type) {
      case "task_complete":
        return <CheckCircle className="h-4 w-4 text-green-400" />;
      case "invitation":
        return <Bell className="h-4 w-4 text-violet-400" />;
      case "mention":
        return <Info className="h-4 w-4 text-blue-400" />;
      case "cost_alert":
        return <AlertCircle className="h-4 w-4 text-yellow-400" />;
      default:
        return <Info className="h-4 w-4 text-gray-400" />;
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case "urgent":
        return "bg-red-500";
      case "high":
        return "bg-orange-500";
      case "normal":
        return "bg-blue-500";
      default:
        return "bg-gray-500";
    }
  };

  return (
    <div className="relative">
      <Button
        variant="ghost"
        size="icon"
        className="relative"
        onClick={() => setIsOpen(!isOpen)}
      >
        <Bell className="h-5 w-5" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 h-5 w-5 rounded-full bg-red-500 text-white text-xs flex items-center justify-center">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </Button>

      {isOpen && (
        <div className="absolute right-0 top-full mt-2 w-96 bg-slate-800 border border-white/10 rounded-xl shadow-2xl z-50">
          <div className="flex items-center justify-between p-4 border-b border-white/10">
            <h3 className="text-white font-medium">通知</h3>
            <div className="flex items-center gap-2">
              {unreadCount > 0 && (
                <Button variant="ghost" size="sm" onClick={markAllAsRead}>
                  <Check className="h-4 w-4 mr-1" />
                  全部已读
                </Button>
              )}
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <Settings className="h-4 w-4" />
              </Button>
            </div>
          </div>

          <ScrollArea className="h-96">
            {notifications.length > 0 ? (
              <div className="divide-y divide-white/10">
                {notifications.map((notification) => (
                  <div
                    key={notification.id}
                    className={`p-4 hover:bg-white/5 transition-colors cursor-pointer ${
                      !notification.is_read ? "bg-white/5" : ""
                    }`}
                    onClick={() => {
                      if (!notification.is_read) {
                        markAsRead(notification.id);
                      }
                      if (notification.action_url) {
                        window.open(notification.action_url, "_blank");
                      }
                    }}
                  >
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5">{getIcon(notification.type)}</div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="text-white font-medium text-sm">
                            {notification.title}
                          </p>
                          {!notification.is_read && (
                            <span className={`h-2 w-2 rounded-full ${getPriorityColor(notification.priority)}`} />
                          )}
                        </div>
                        <p className="text-white/60 text-sm mt-1 line-clamp-2">
                          {notification.message}
                        </p>
                        <p className="text-white/40 text-xs mt-2">
                          {formatDistanceToNow(new Date(notification.created_at), {
                            addSuffix: true,
                            locale: zhCN,
                          })}
                        </p>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 opacity-0 group-hover:opacity-100"
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteNotification(notification.id);
                        }}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-64 text-white/40">
                <Bell className="h-12 w-12 mb-2" />
                <p>暂无通知</p>
              </div>
            )}
          </ScrollArea>
        </div>
      )}
    </div>
  );
}