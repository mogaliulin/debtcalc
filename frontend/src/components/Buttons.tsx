import { Link } from "react-router-dom";

interface MainButtonProps {
  text: string;
  onClick: () => void;
  disabled?: boolean;
  loading?: boolean;
}

/** Главная кнопка экрана, закреплённая внизу. */
export function MainButton({ text, onClick, disabled = false, loading = false }: MainButtonProps) {
  return (
    <>
      <div className="main-button-spacer" />
      <div className="main-button-bar">
        <button className="btn btn-primary btn-block" disabled={disabled || loading} onClick={onClick}>
          {loading ? "Подождите…" : text}
        </button>
      </div>
    </>
  );
}

export function BackButton({ to }: { to: string }) {
  return (
    <Link className="back-link" to={to}>
      ‹ Назад
    </Link>
  );
}
