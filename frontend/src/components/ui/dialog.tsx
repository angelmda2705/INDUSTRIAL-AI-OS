"use client";

import { X } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";

/** Accessible modal built on the native <dialog> element (focus trap and Esc handled by the browser). */
export function Dialog({ open, onClose, title, children, footer }: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    if (!open && el.open) el.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      className="m-auto w-[min(92vw,36rem)] rounded-lg border border-line bg-panel p-0 text-ink shadow-xl"
      aria-labelledby="dialog-title"
    >
      <div className="flex items-center justify-between border-b border-line px-5 py-3">
        <h2 id="dialog-title" className="text-sm font-semibold">
          {title}
        </h2>
        <button type="button" onClick={onClose} className="rounded p-1 text-muted hover:bg-slate-100" aria-label="Cerrar">
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="max-h-[70vh] overflow-y-auto px-5 py-4">{children}</div>
      {footer && <div className="flex justify-end gap-2 border-t border-line px-5 py-3">{footer}</div>}
    </dialog>
  );
}
