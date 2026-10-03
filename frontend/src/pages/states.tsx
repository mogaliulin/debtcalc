export function Loading() {
  return (
    <div className="page center">
      <div className="spinner" aria-label="Загрузка" />
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: Error; onRetry?: () => void }) {
  return (
    <div className="page center">
      <p>{error.message}</p>
      {onRetry && (
        <button className="btn btn-plain" onClick={onRetry}>
          Повторить
        </button>
      )}
    </div>
  );
}
