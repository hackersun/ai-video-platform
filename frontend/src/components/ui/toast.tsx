'use client';

import { useEffect, useState, useCallback, createContext, useContext, ReactNode } from 'react';

// ========== 类型定义 ==========

export type ToastType = 'success' | 'error' | 'info';

export type ToastOptions = {
  title: string;
  description?: string;
  type?: ToastType;
};

export type ToastItem = ToastOptions & {
  id: string;
};

// ========== Context ==========

type ToastContextValue = {
  toast: (options: ToastOptions) => void;
};

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

// ========== Provider ==========

const AUTO_DISMISS_MS = 4000;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(
    (options: ToastOptions) => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
      const item: ToastItem = { id, type: 'info', ...options };
      setToasts((prev) => [...prev, item]);
    },
    []
  );

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <ToastContainer toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}

// ========== Hook ==========

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (context === undefined) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
}

// ========== Container ==========

function ToastContainer({
  toasts,
  onDismiss,
}: {
  toasts: ToastItem[];
  onDismiss: (id: string) => void;
}) {
  return (
    <div
      style={{
        position: 'fixed',
        bottom: '1.5rem',
        right: '1.5rem',
        zIndex: 9999,
        display: 'flex',
        flexDirection: 'column',
        gap: '0.5rem',
        pointerEvents: 'none',
      }}
    >
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

// ========== Individual Toast ==========

function ToastItem({
  toast,
  onDismiss,
}: {
  toast: ToastItem;
  onDismiss: (id: string) => void;
}) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Trigger enter animation
    const show = requestAnimationFrame(() => setVisible(true));

    const timer = setTimeout(() => {
      setVisible(false);
      setTimeout(() => onDismiss(toast.id), 300); // fade-out duration
    }, AUTO_DISMISS_MS);

    return () => {
      cancelAnimationFrame(show);
      clearTimeout(timer);
    };
  }, [toast.id, onDismiss]);

  const borderColor = {
    success: '#22c55e',
    error: '#ef4444',
    info: '#3b82f6',
  }[toast.type || 'info'];

  const icon = {
    success: '\u2713',
    error: '\u2717',
    info: 'i',
  }[toast.type || 'info'];

  const iconColor = borderColor;

  return (
    <div
      style={{
        backgroundColor: '#fff',
        border: `1px solid ${borderColor}`,
        borderLeft: `4px solid ${borderColor}`,
        borderRadius: '0.5rem',
        boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
        padding: '0.75rem 1rem',
        minWidth: '280px',
        maxWidth: '400px',
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateX(0)' : 'translateX(100%)',
        transition: 'opacity 0.3s ease, transform 0.3s ease',
        pointerEvents: 'auto',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
        <div
          style={{
            width: '1.5rem',
            height: '1.5rem',
            borderRadius: '50%',
            border: `2px solid ${iconColor}`,
            color: iconColor,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '0.75rem',
            fontWeight: 700,
            flexShrink: 0,
          }}
        >
          {icon}
        </div>
        <div style={{ flex: 1 }}>
          <p
            style={{
              margin: 0,
              fontSize: '0.875rem',
              fontWeight: 600,
              color: '#1f2937',
            }}
          >
            {toast.title}
          </p>
          {toast.description && (
            <p
              style={{
                margin: '0.25rem 0 0',
                fontSize: '0.8125rem',
                color: '#6b7280',
              }}
            >
              {toast.description}
            </p>
          )}
        </div>
        <button
          onClick={() => {
            setVisible(false);
            setTimeout(() => onDismiss(toast.id), 300);
          }}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: '#9ca3af',
            fontSize: '1rem',
            padding: '0 0 0 0.5rem',
            lineHeight: 1,
          }}
        >
          {'\u00d7'}
        </button>
      </div>
    </div>
  );
}
