"""
WebSocket 实时协作 Hook
"""

import { useEffect, useRef, useState, useCallback } from "react";

interface CollaborationUser {
  id: string;
  username: string;
  color: string;
  cursor_position: number;
}

interface UseCollaborationOptions {
  roomId: string;
  token: string;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onUserJoin?: (user: CollaborationUser) => void;
  onUserLeave?: (userId: string) => void;
  onContentUpdate?: (content: string, userId: string) => void;
  onCursorMove?: (userId: string, position: number) => void;
  onError?: (error: string) => void;
}

export function useCollaboration(options: UseCollaborationOptions) {
  const { roomId, token, onConnect, onDisconnect, onUserJoin, onUserLeave, onContentUpdate, onCursorMove, onError } = options;
  
  const wsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [users, setUsers] = useState<CollaborationUser[]>([]);
  const [lockOwner, setLockOwner] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const wsUrl = `${process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000"}/ws/collaborate/${roomId}?token=${token}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setIsConnected(true);
      setError(null);
      onConnect?.();
    };

    ws.onclose = () => {
      setIsConnected(false);
      onDisconnect?.();
    };

    ws.onerror = (e) => {
      setError("连接失败");
      onError?.("连接失败");
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        handleMessage(message);
      } catch (e) {
        console.error("解析消息失败:", e);
      }
    };

    wsRef.current = ws;
  }, [roomId, token, onConnect, onDisconnect, onError]);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const handleMessage = (message: any) => {
    switch (message.type) {
      case "connected":
        if (message.room_info) {
          setUsers(message.room_info.users || []);
          setLockOwner(message.room_info.lock_owner);
        }
        break;

      case "user_join":
        setUsers((prev) => [...prev, message.user]);
        onUserJoin?.(message.user);
        break;

      case "user_leave":
        setUsers((prev) => prev.filter((u) => u.id !== message.user_id));
        onUserLeave?.(message.user_id);
        break;

      case "content_update":
        onContentUpdate?.(message.content, message.user_id);
        break;

      case "cursor_move":
        onCursorMove?.(message.user_id, message.position);
        break;

      case "edit_lock":
        setLockOwner(message.user_id);
        break;

      case "edit_unlock":
        setLockOwner(null);
        break;

      case "error":
        setError(message.message);
        onError?.(message.message);
        break;
    }
  };

  const sendMessage = useCallback((type: string, data: any = {}) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, ...data }));
    }
  }, []);

  const updateContent = useCallback((content: string, cursorPosition: number) => {
    sendMessage("content_update", { content, cursor_position: cursorPosition });
  }, [sendMessage]);

  const updateCursor = useCallback((position: number, selectionStart?: number, selectionEnd?: number) => {
    sendMessage("cursor_move", { position, selection_start: selectionStart, selection_end: selectionEnd });
  }, [sendMessage]);

  const requestEditLock = useCallback(() => {
    sendMessage("edit_lock", {});
  }, [sendMessage]);

  const releaseEditLock = useCallback(() => {
    sendMessage("edit_unlock", {});
  }, [sendMessage]);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return {
    isConnected,
    users,
    lockOwner,
    error,
    updateContent,
    updateCursor,
    requestEditLock,
    releaseEditLock,
  };
}