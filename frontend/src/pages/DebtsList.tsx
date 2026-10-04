import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Debt, DebtList, Me } from "../api/types";
import { Avatar } from "../components/Avatar";
import { DebtCard } from "../components/DebtCard";
import { MainButton } from "../components/Buttons";
import { useCurrentList } from "../currentList";
import { ROLE_LABEL, formatDate, money } from "../format";
import { ErrorState, Loading } from "./states";

function nearestPayment(debts: Debt[]) {
  return debts
    .map((d) => d.summary.next_payment && { debt: d, row: d.summary.next_payment })
    .filter((x): x is NonNullable<typeof x> => Boolean(x))
    .sort((a, b) => a.row.date.localeCompare(b.row.date))[0];
}

function ListSwitcher({ lists, current, onSelect }: { lists: DebtList[]; current: DebtList; onSelect: (id: number) => void }) {
  return (
    <div className="chips list-switch" role="tablist" aria-label="Списки долгов">
      {lists.map((l) => (
        <button
          key={l.owner.user_id}
          role="tab"
          aria-selected={l === current}
          className={`chip ${l === current ? "chip-on" : ""}`}
          onClick={() => onSelect(l.owner.user_id)}
        >
          {l.is_own ? "Мой список" : l.owner.display_name}
        </button>
      ))}
    </div>
  );
}

export function DebtsList({ me }: { me: Me }) {
  const navigate = useNavigate();
  const { lists, current, select } = useCurrentList();
  const listId = current?.owner.user_id;
  const debtsQuery = useQuery({
    queryKey: ["debts", listId],
    queryFn: () => api.debts(listId),
    enabled: listId !== undefined,
  });

  if (lists.isPending || (listId !== undefined && debtsQuery.isPending)) return <Loading />;
  if (lists.error) return <ErrorState error={lists.error} onRetry={lists.refetch} />;
  if (debtsQuery.error) return <ErrorState error={debtsQuery.error} onRetry={debtsQuery.refetch} />;
  if (!current || !debtsQuery.data) return <Loading />;

  const debts = debtsQuery.data;
  const canEdit = current.role !== "viewer";
  const active = debts.filter((d) => !d.summary.is_closed);
  const closed = debts.filter((d) => d.summary.is_closed);
  const totalRemaining = active.reduce((sum, d) => sum + Number(d.summary.remaining_balance), 0);
  const nearest = nearestPayment(active);

  return (
    <div className="page">
      <header className="page-header">
        <h1>{current.is_own ? "Мои долги" : `Долги: ${current.owner.display_name}`}</h1>
        <Link to="/settings" className="avatar-link" aria-label="Профиль и настройки" title={me.display_name}>
          <Avatar user={me} />
        </Link>
      </header>

      {lists.data.length > 1 && <ListSwitcher lists={lists.data} current={current} onSelect={select} />}

      {!current.is_own && (
        <div className="banner banner-info shared-banner">
          <Avatar user={current.owner} size={24} />
          <span>
            Список ведёт {current.owner.display_name} · у вас {ROLE_LABEL[current.role]}
          </span>
        </div>
      )}

      {debts.length === 0 ? (
        <div className="empty">
          <div className="empty-icon" aria-hidden>
            💳
          </div>
          <p>Пока нет ни одного долга.</p>
          {canEdit && <p className="hint">Добавьте кредит или заём, чтобы увидеть график платежей.</p>}
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
      {canEdit && (
        <MainButton
          text="Добавить долг"
          onClick={() => navigate(current.is_own ? "/debts/new" : `/debts/new?list=${current.owner.user_id}`)}
        />
      )}
    </div>
  );
}
