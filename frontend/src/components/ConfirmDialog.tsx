import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

type Confirm = (message: string) => Promise<boolean>;

const ConfirmContext = createContext<Confirm>(async () => false);

interface Pending {
  message: string;
  resolve: (ok: boolean) => void;
}

/** Диалог подтверждения опасных действий (удаление и т.п.). */
export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<Pending | null>(null);

  const confirm = useCallback<Confirm>((message) => new Promise((resolve) => setPending({ message, resolve })), []);

  const close = (ok: boolean) => {
    pending?.resolve(ok);
    setPending(null);
  };

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      {pending && (
        <div className="dialog-backdrop" onClick={() => close(false)}>
          <div className="dialog" role="alertdialog" onClick={(e) => e.stopPropagation()}>
            <p>{pending.message}</p>
            <div className="dialog-actions">
              <button className="btn btn-plain" onClick={() => close(false)}>
                Отмена
              </button>
              <button className="btn btn-danger" onClick={() => close(true)} autoFocus>
                OK
              </button>
            </div>
          </div>
        </div>
      )}
    </ConfirmContext.Provider>
  );
}

export function useConfirm(): Confirm {
  return useContext(ConfirmContext);
}

export function notify(message: string): void {
  window.alert(message);
}
