'use client';

import {
  useEffect,
  useState,
  useCallback,
  createContext,
  useContext,
  ReactNode,
} from 'react';
import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react';

export type ToastType = 'success' | 'error' | 'info';

export type ToastOptions = {
  title: string;
  description?: string;
  type?: ToastType;
};

export type ToastItem = ToastOptions & {
  id: string;
};

type ToastContextValue = {
  toast: (options: ToastOptions) => void;
};

const ToastContext = createContext<ToastContextValue | undefined>(undefined);
const AUTO_DISMISS_MS = 4000;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback((options: ToastOptions) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
    setToasts((prev) => [...prev, { id, type: 'info', ...options }]);
  }, []);

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <ToastContainer toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (context === undefined) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
}

function ToastContainer({
  toasts,
  onDismiss,
}: {
  toasts: ToastItem[];
  onDismiss: (id: string) => void;
}) {
  return (
    <div
      aria-live="polite"
      aria-atomic="true"
      className="fixed bottom-4 left-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none sm:left-auto sm:right-4 sm:w-[24rem]"
    >
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

function ToastItem({
  toast,
  onDismiss,
}: {
  toast: ToastItem;
  onDismiss: (id: string) => void;
}) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const show = requestAnimationFrame(() => setVisible(true));
    const hide = window.setTimeout(() => {
      setVisible(false);
      window.setTimeout(() => onDismiss(toast.id), 200);
    }, AUTO_DISMISS_MS);

    return () => {
      cancelAnimationFrame(show);
      clearTimeout(hide);
    };
  }, [toast.id, onDismiss]);

  const variant = toast.type || 'info';
  const meta = {
    success: {
      icon: CheckCircle2,
      border: 'border-emerald-500/30',
      text: 'text-emerald-300',
      accent: 'from-emerald-500/15',
    },
    error: {
      icon: AlertCircle,
      border: 'border-rose-500/30',
      text: 'text-rose-300',
      accent: 'from-rose-500/15',
    },
    info: {
      icon: Info,
      border: 'border-sky-500/30',
      text: 'text-sky-300',
      accent: 'from-sky-500/15',
    },
  }[variant];

  const Icon = meta.icon;

  return (
    <div
      role="status"
      className={`pointer-events-auto overflow-hidden rounded-2xl border bg-slate-950/95 shadow-2xl backdrop-blur-xl transition-[opacity,transform] duration-200 ${meta.border} ${
        visible ? 'translate-y-0 opacity-100' : 'translate-y-2 opacity-0'
      }`}
    >
      <div className={`h-1 bg-gradient-to-r ${meta.accent} to-transparent`} />
      <div className="flex items-start gap-3 p-4">
        <div className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border ${meta.border} ${meta.text}`}>
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-white">{toast.title}</p>
          {toast.description && (
            <p className="mt-1 text-sm leading-5 text-white/60">{toast.description}</p>
          )}
        </div>
        <button
          type="button"
          aria-label="关闭提示"
          onClick={() => {
            setVisible(false);
            window.setTimeout(() => onDismiss(toast.id), 200);
          }}
          className="rounded-full p-1 text-white/45 transition-colors hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
