"use client";

import { useCallback, useEffect } from "react";

export type ToastItem = {
  id: string;
  message: string;
  type: "success" | "warning" | "info";
};

type Props = {
  toasts: ToastItem[];
  onDismiss: (id: string) => void;
};

export function ToastStack({ toasts, onDismiss }: Props) {
  if (!toasts.length) return null;
  return (
    <div className="toastStack">
      {toasts.map((t) => (
        <ToastBubble key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

function ToastBubble({
  toast,
  onDismiss,
}: {
  toast: ToastItem;
  onDismiss: (id: string) => void;
}) {
  const dismiss = useCallback(() => onDismiss(toast.id), [toast.id, onDismiss]);

  useEffect(() => {
    const t = setTimeout(dismiss, 6000);
    return () => clearTimeout(t);
  }, [dismiss]);

  return (
    <div className={`toast toast--${toast.type}`}>
      <span style={{ flex: 1 }}>{toast.message}</span>
      <button className="toastClose" onClick={dismiss}>×</button>
    </div>
  );
}
