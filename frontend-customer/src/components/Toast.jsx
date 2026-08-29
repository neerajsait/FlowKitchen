import React, { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { CheckCircle, XCircle, AlertCircle, X } from "../ui/Icon";

const icons = {
  success: <CheckCircle size={18} />,
  error:   <XCircle size={18} />,
  warning: <AlertCircle size={18} />,
};

export default function Toast({ toast, onDismiss }) {
  const timerRef = useRef(null);

  useEffect(() => {
    if (toast) {
      timerRef.current = setTimeout(() => onDismiss(), 3500);
    }
    return () => clearTimeout(timerRef.current);
  }, [toast]);

  if (!toast) return null;

  const cls = toast.type === "error" ? "toast-error" : toast.type === "warning" ? "toast-warning" : "toast-success";

  return createPortal(
    <div className="toast-container">
      <div className={`toast ${cls}`} role="alert">
        {icons[toast.type] || icons.success}
        <span style={{ flex: 1, lineHeight: 1.4 }}>{toast.message}</span>
        <button onClick={onDismiss} style={{ background: "none", border: "none", cursor: "pointer", color: "inherit", opacity: 0.8, padding: "0 0 0 0.25rem", display: "flex" }}>
          <X size={14} />
        </button>
      </div>
    </div>,
    document.body
  );
}
