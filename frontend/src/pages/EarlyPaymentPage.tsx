import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { EarlyMode } from "../api/types";
import { BackButton, MainButton } from "../components/Buttons";
import { formatDate, money, normalizeNumber, todayIso } from "../format";
import { ErrorState, Loading } from "./states";

const MODES: { value: EarlyMode; title: string; description: string }[] = [
  {
    value: "reduce_term",
    title: "Уменьшить срок",
    description: "Платёж остаётся прежним, кредит закроется раньше. Обычно выгоднее — меньше переплата.",
  },
  {
    value: "reduce_payment",
    title: "Уменьшить платёж",
    description: "Срок прежний, ежемесячный платёж станет меньше.",
  },
];

export function EarlyPaymentPage() {
  const debtId = Number(useParams().id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const debt = useQuery({ queryKey: ["debt", debtId], queryFn: () => api.debt(debtId) });

  const [date, setDate] = useState(todayIso());
  const [amount, setAmount] = useState("");
  const [mode, setMode] = useState<EarlyMode>("reduce_term");

  const save = useMutation({
    mutationFn: () => api.addEarlyPayment(debtId, { date, amount: normalizeNumber(amount), mode }),
    onSuccess: (schedule) => {
      queryClient.setQueryData(["schedule", debtId], schedule);
      queryClient.invalidateQueries({ queryKey: ["debt", debtId] });
      queryClient.invalidateQueries({ queryKey: ["debts"] });
      navigate(`/debts/${debtId}`, { replace: true });
    },
  });

  if (debt.isPending) return <Loading />;
  if (debt.error) return <ErrorState error={debt.error} onRetry={debt.refetch} />;

  const amountNumber = Number(normalizeNumber(amount));
  const invalid = !date || !amount || !Number.isFinite(amountNumber) || amountNumber <= 0;
  const { summary } = debt.data;
  if (debt.data.role === "viewer") {
    return (
      <div className="page">
        <BackButton to={`/debts/${debtId}`} />
        <p className="hint center-text">У вас доступ к этому списку только для просмотра.</p>
      </div>
    );
  }

  return (
    <div className="page">
      <BackButton to={`/debts/${debtId}`} />
      <header className="page-header">
        <h1>Досрочный платёж</h1>
      </header>
      <p className="hint">
        {debt.data.name} · остаток {money(summary.remaining_balance)}
        {summary.next_payment && <> · след. платёж {formatDate(summary.next_payment.date)}</>}
      </p>

      <section className="card form">
        <label className="field">
          <span>Дата</span>
          <input type="date" value={date} min={debt.data.start_date} onChange={(e) => setDate(e.target.value)} />
        </label>
        <label className="field">
          <span>Сумма, ₽</span>
          <input
            inputMode="decimal"
            autoFocus
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="100 000"
          />
        </label>
        <p className="hint">
          Если дата не совпадает с датой платежа, из суммы сначала гасятся проценты, начисленные к этому дню, остальное
          идёт в счёт основного долга.
        </p>
      </section>

      <div className="mode-list">
        {MODES.map((m) => (
          <button
            key={m.value}
            className={`card mode ${mode === m.value ? "mode-on" : ""}`}
            onClick={() => setMode(m.value)}
            aria-pressed={mode === m.value}
          >
            <span className="radio" aria-hidden />
            <span>
              <b>{m.title}</b>
              <span className="hint mode-desc">{m.description}</span>
            </span>
          </button>
        ))}
      </div>

      {save.error && <p className="error">{save.error.message}</p>}

      <MainButton text="Внести платёж" onClick={() => !invalid && save.mutate()} disabled={invalid} loading={save.isPending} />
    </div>
  );
}
