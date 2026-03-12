"use client";

import { useEffect, useState } from "react";
import { X, CheckCircle, AlertCircle, Info } from "lucide-react";
import { cn } from "@/lib/utils";

interface Toast {
  id: string;
  title: string;
  description?: string;
  variant?: "default" | "success" | "error" | "info";
}

const toastStore = {
  toasts: [] as Toast[],
  listeners: [] as ((toasts: Toast[]) => void)[],
  
  subscribe(listener: (toasts: Toast[]) => void) {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter((l) => l !== listener);
    };
  },
  
  notify(toast: Omit<Toast, "id">) {
    const id = Math.random().toString(36).substring(7);
    const newToast = { ...toast, id };
    this.toasts = [...this.toasts, newToast];
    this.listeners.forEach((l) => l(this.toasts));
    
    setTimeout(() => {
      this.dismiss(id);
    }, 5000);
  },
  
  dismiss(id: string) {
    this.toasts = this.toasts.filter((t) => t.id !== id);
    this.listeners.forEach((l) => l(this.toasts));
  },
};

export function toast(props: Omit<Toast, "id">) {
  toastStore.notify(props);
}

export function Toaster() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(() => {
    return toastStore.subscribe(setToasts);
  }, []);

  const icons = {
    default: Info,
    success: CheckCircle,
    error: AlertCircle,
    info: Info,
  };

  const variants = {
    default: "border-white/10 bg-white/5",
    success: "border-green-500/30 bg-green-500/10",
    error: "border-red-500/30 bg-red-500/10",
    info: "border-blue-500/30 bg-blue-500/10",
  };

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => {
        const Icon = icons[toast.variant || "default"];
        return (
          <div
            key={toast.id}
            className={cn(
              "flex items-start gap-3 rounded-lg border p-4 shadow-lg backdrop-blur-xl min-w-[300px] max-w-[400px] animate-fade-in",
              variants[toast.variant || "default"]
            )}
          >
            <Icon className="h-5 w-5 shrink-0 mt-0.5" />
            <div className="flex-1">
              <h4 className="text-sm font-medium text-white">{toast.title}</h4>
              {toast.description && (
                <p className="text-sm text-white/60 mt-1">{toast.description}</p>
              )}
            </div>
            <button
              onClick={() => toastStore.dismiss(toast.id)}
              className="shrink-0 text-white/40 hover:text-white transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
