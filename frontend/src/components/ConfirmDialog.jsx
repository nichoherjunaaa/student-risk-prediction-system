import React from "react";
import { AlertTriangle } from "lucide-react";
import Button from "./Button";

// Pengganti window.confirm()/alert() bawaan browser, supaya konfirmasi
// bertema sama dengan modal yang sudah dipakai di halaman Master Model.
const ConfirmDialog = ({
  open,
  title,
  message,
  confirmLabel = "Ya, Lanjutkan",
  cancelLabel = "Batal",
  variant = "danger",
  onConfirm,
  onCancel,
}) => {
  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
    >
      <div className="bg-surface rounded-2xl shadow-xl border border-border w-full max-w-md p-6">
        <div className="flex flex-col items-center text-center">
          <div className="h-16 w-16 bg-red-100 rounded-full flex items-center justify-center mb-4 border border-red-200">
            <AlertTriangle className="h-8 w-8 text-red-600" />
          </div>
          <h3 className="text-xl font-bold text-secondary mb-2">{title}</h3>
          <p className="text-gray-600 mb-6 text-sm">{message}</p>
          <div className="flex gap-3 w-full">
            {onCancel && (
              <Button variant="secondary" size="lg" block onClick={onCancel}>
                {cancelLabel}
              </Button>
            )}
            <Button variant={variant} size="lg" block onClick={onConfirm}>
              {confirmLabel}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ConfirmDialog;
