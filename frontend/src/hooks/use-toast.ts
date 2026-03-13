"use client";

import { useCallback } from "react";
import { toast as toastFn } from "@/components/ui/toaster";

export function useToast() {
  const toast = useCallback(
    (props: {
      title: string;
      description?: string;
      variant?: "default" | "success" | "error" | "info";
    }) => {
      toastFn(props);
    },
    []
  );

  return { toast };
}