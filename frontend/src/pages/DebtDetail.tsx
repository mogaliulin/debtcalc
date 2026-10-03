import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { Schedule, ScheduleRow } from "../api/types";
import { notify, useConfirm } from "../components/ConfirmDialog";
import { ProgressBar } from "../components/ProgressBar";
import { ScheduleList, rowKey } from "../components/ScheduleList";
import { BackButton, MainButton } from "../components/Buttons";
import { SCHEDULE_LABEL, formatDate, money, pluralMonths, rate } from "../format";
import { ErrorState, Loading } from "./states";

export function DebtDetail() {
  const debtId = Number(useParams().id);
  const navigate = useNavigate();
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const [hidePaid, setHidePaid] = useState(false);
  const [editingName, setEditingName] = useState<string | null>(null);

  const debt = useQuery({ queryKey: ["debt", debtId], queryFn: () => api.debt(debtId) });
  const schedule = useQuery({ queryKey: ["schedule", debtId], queryFn: () => api.schedule(debtId) });

  const applySchedule = (data: Schedule) => {
    queryClient.setQueryData(["schedule", debtId], data);
    queryClient.invalidateQueries({ queryKey: ["debt", debtId] });
    queryClient.invalidateQueries({ queryKey: ["debts"] });
  };
  const onFail = (error: Error) => {
    notify(error.message);
  };

  const togglePaid = useMutation({
    mutationFn: (row: ScheduleRow) => api.setPaid(debtId, row.period_no!, !row.is_paid),
    onSuccess: (data) => {
      applySchedule(data);
    },
    onError: onFail,
  });

  const deleteEarly = useMutation({
    mutationFn: (row: ScheduleRow) => api.deleteEarlyPayment(debtId, row.early_payment_id!),
    onSuccess: (data) => {
      applySchedule(data);
    },
    onError: onFail,
  });

  const rename = useMutation({
    mutationFn: (name: string) => api.renameDebt(debtId, name),
    onSuccess: (data) => {
      queryClient.setQueryData(["debt", debtId], data);
      queryClient.invalidateQueries({ queryKey: ["debts"] });
      setEditingName(null);
    },
    onError: onFail,
  });

  const remove = useMutation({
    mutationFn: () => api.deleteDebt(debtId),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: ["debt", debtId] });
      queryClient.removeQueries({ queryKey: ["schedule", debtId] });
      queryClient.invalidateQueries({ queryKey: ["debts"] });
      navigate("/", { replace: true });
    },
    onError: onFail,
  });

  if (debt.isPending || schedule.isPending) return <Loading />;
  if (debt.error) return <ErrorState error={debt.error} onRetry={debt.refetch} />;
  if (schedule.error) return <ErrorState error={schedule.error} onRetry={schedule.refetch} />;

  const d = debt.data;
  const { rows, summary } = schedule.data;
  const next = summary.next_payment;
  const visibleRows = hidePaid ? rows.filter((r) => !r.is_paid) : rows;
  const busyKey =
    (togglePaid.isPending && togglePaid.variables && rowKey(togglePaid.variables)) ||
    (deleteEarly.isPending && deleteEarly.variables && rowKey(deleteEarly.variables)) ||
    null;

  const onDeleteEarly = async (row: ScheduleRow) => {
    if (await confirm(`Удалить досрочный платёж ${money(row.payment)} от ${formatDate(row.date)}? График будет пересчитан.`)) {
      deleteEarly.mutate(row);
    }
  };
  const onDeleteDebt = async () => {
    if (await confirm(`Удалить «${d.name}» вместе с графиком и всеми отметками?`)) remove.mutate();
  };
  const onTogglePaid = async (row: ScheduleRow) => {
    if (row.is_paid && !(await confirm(`Снять отметку об оплате платежа №${row.period_no}?`))) return;
    togglePaid.mutate(row);
  };

  return (
    <div className="page">
      <BackButton to="/" />
      <header className="page-header">
        {editingName === null ? (
          <>
            <h1>{d.name}</h1>
            <button className="icon-btn" aria-label="Переименовать" onClick={() => setEditingName(d.name)}>
              ✎
            </button>
          </>
        ) : (
          <form
            className="rename"
            onSubmit={(e) => {
              e.preventDefault();
              if (editingName.trim()) rename.mutate(editingName.trim());
            }}
          >
            <input autoFocus value={editingName} maxLength={100} onChange={(e) => setEditingName(e.target.value)} />
            <button className="btn btn-primary" disabled={!editingName.trim() || rename.isPending}>
              OK
            </button>
            <button type="button" className="btn btn-plain" onClick={() => setEditingName(null)}>
              ✕
            </button>
          </form>
        )}
      </header>

      <section className="card">
        <div className="hint">Остаток основного долга</div>
        <div className="big-value">{money(summary.remaining_balance)}</div>
        <ProgressBar value={summary.progress} />
        <div className="hint progress-caption">
          Погашено {Math.round(summary.progress * 100)}% · оплачено {summary.paid_count} из {summary.periods_count}
        </div>

        {summary.overdue_count > 0 && (
          <div className="banner banner-danger">
            Не отмечено как оплаченные: {summary.overdue_count}. Отметьте прошедшие платежи в графике ниже.
          </div>
        )}

        <div className="stat-grid">
          <div>
            <div className="hint">Следующий платёж</div>
            <div className="stat-value">{next ? money(next.payment) : "—"}</div>
            {next && <div className="hint">{formatDate(next.date)}</div>}
          </div>
          <div>
            <div className="hint">Дата закрытия</div>
            <div className="stat-value">{formatDate(summary.close_date)}</div>
          </div>
          <div>
            <div className="hint">Переплата по %</div>
            <div className="stat-value">{money(summary.total_interest)}</div>
          </div>
          <div>
            <div className="hint">Условия</div>
            <div className="stat-value">
              {money(d.principal, true)} · {rate(d.annual_rate)}
            </div>
            <div className="hint">
              {pluralMonths(d.term_months)} · {SCHEDULE_LABEL[d.schedule_type].toLowerCase()}
            </div>
          </div>
        </div>
      </section>

      <div className="section-head">
        <h2 className="section-title">График платежей</h2>
        <label className="toggle-inline">
          <input type="checkbox" checked={hidePaid} onChange={(e) => setHidePaid(e.target.checked)} />
          Скрыть оплаченные
        </label>
      </div>
      <section className="card card-flush">
        {visibleRows.length ? (
          <ScheduleList rows={visibleRows} onTogglePaid={onTogglePaid} onDeleteEarly={onDeleteEarly} busyKey={busyKey} />
        ) : (
          <p className="hint center-text">Все платежи оплачены 🎉</p>
        )}
      </section>

      <button className="btn btn-danger-plain btn-block" onClick={onDeleteDebt} disabled={remove.isPending}>
        Удалить долг
      </button>

      {!summary.is_closed && (
        <MainButton text="Досрочный платёж" onClick={() => navigate(`/debts/${debtId}/early`)} />
      )}
    </div>
  );
}
