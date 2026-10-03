import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Debt, Me } from "../api/types";
import { Avatar } from "../components/Avatar";
import { DebtCard } from "../components/DebtCard";
import { MainButton } from "../components/Buttons";
import { formatDate, money } from "../format";
import { ErrorState, Loading } from "./states";

function nearestPayment(debts: Debt[]) {
  return debts
    .map((d) => d.summary.next_payment && { debt: d, row: d.summary.next_payment })
    .filter((x): x is NonNullable<typeof x> => Boolean(x))
    .sort((a, b) => a.row.date.localeCompare(b.row.date))[0];
}

export function DebtsList({ me }: { me: Me }) {
  const navigate = useNavigate();
  const { data: debts, isPending, error, refetch } = useQuery({ queryKey: ["debts"], queryFn: api.debts });

  const addButton = <MainButton text="Добавить долг" onClick={() => navigate("/debts/new")} />;

  if (isPending) return <Loading />;
  if (error) return <ErrorState error={error} onRetry={refetch} />;

  const active = debts.filter((d) => !d.summary.is_closed);
  const closed = debts.filter((d) => d.summary.is_closed);
  const totalRemaining = active.reduce((sum, d) => sum + Number(d.summary.remaining_balance), 0);
  const nearest = nearestPayment(active);

  return (
    <div className="page">
      <header className="page-header">
        <h1>Мои долги</h1>
        <Link to="/settings" className="avatar-link" aria-label="Профиль и настройки" title={me.display_name}>
          <Avatar me={me} />
        </Link>
      </header>

      {debts.length === 0 ? (
        <div className="empty">
          <div className="empty-icon" aria-hidden>
            💳
          </div>
          <p>Пока нет ни одного долга.</p>
          <p className="hint">Добавьте кредит или заём, чтобы увидеть график платежей.</p>
        </div>
      ) : (
        <>
          {active.length > 0 && (
            <section className="card totals">
              <div>
                <div className="hint">Общий остаток</div>
                <div className="totals-value">{money(totalRemaining)}</div>
              </div>
              {nearest && (
                <div>
                  <div className="hint">Ближайший платёж</div>
                  <div className="totals-next">
                    {money(nearest.row.payment)} · {formatDate(nearest.row.date)}
                  </div>
                  <div className="hint">{nearest.debt.name}</div>
                </div>
              )}
            </section>
          )}

          {active.map((d) => (
            <DebtCard key={d.id} debt={d} />
          ))}

          {closed.length > 0 && (
            <>
              <h2 className="section-title">Погашенные</h2>
              {closed.map((d) => (
                <DebtCard key={d.id} debt={d} />
              ))}
            </>
          )}
        </>
      )}
      {addButton}
    </div>
  );
}
