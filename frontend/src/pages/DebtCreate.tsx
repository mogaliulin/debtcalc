import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { LoanInput, ScheduleType } from "../api/types";
import { ScheduleList } from "../components/ScheduleList";
import { useLists } from "../currentList";
import { BackButton, MainButton } from "../components/Buttons";
import { SCHEDULE_LABEL, addMonthsIso, formatDate, money, normalizeNumber, pluralMonths, todayIso } from "../format";

const TERM_PRESETS = [12, 24, 36, 60, 120, 240];

function useDebounced<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

function validate(loan: LoanInput): string | null {
  const principal = Number(loan.principal);
  const rate = Number(loan.annual_rate);
  if (!loan.principal || !Number.isFinite(principal) || principal <= 0) return "Укажите сумму долга";
  if (loan.annual_rate === "" || !Number.isFinite(rate) || rate < 0 || rate > 999) return "Укажите ставку";
  if (!Number.isInteger(loan.term_months) || loan.term_months < 1 || loan.term_months > 600)
    return "Срок — от 1 до 600 месяцев";
  if (!loan.start_date || !loan.first_payment_date) return "Укажите даты";
  if (loan.first_payment_date <= loan.start_date) return "Первый платёж должен быть позже даты выдачи";
  return null;
}

export function DebtCreate() {
  const navigate = useNavigate();
  // долг можно добавить и в чужой список, если там есть права на редактирование
  const listParam = Number(useSearchParams()[0].get("list"));
  const listId = Number.isInteger(listParam) && listParam > 0 ? listParam : undefined;
  const targetList = useLists().data?.find((l) => l.owner.user_id === listId);
  const queryClient = useQueryClient();

  const [name, setName] = useState("");
  const [principal, setPrincipal] = useState("");
  const [rate, setRate] = useState("");
  const [term, setTerm] = useState("12");
  const [startDate, setStartDate] = useState(todayIso());
  const [firstPayment, setFirstPayment] = useState(addMonthsIso(todayIso(), 1));
  const [firstPaymentTouched, setFirstPaymentTouched] = useState(false);
  const [scheduleType, setScheduleType] = useState<ScheduleType>("annuity");
  const [showSchedule, setShowSchedule] = useState(false);

  const loan: LoanInput = useMemo(
    () => ({
      principal: normalizeNumber(principal),
      annual_rate: normalizeNumber(rate),
      term_months: Number(term),
      start_date: startDate,
      first_payment_date: firstPayment,
      schedule_type: scheduleType,
    }),
    [principal, rate, term, startDate, firstPayment, scheduleType],
  );
  const loanError = validate(loan);
  const debouncedLoan = useDebounced(loan, 400);
  const debouncedValid = validate(debouncedLoan) === null;

  const preview = useQuery({
    queryKey: ["calculate", debouncedLoan],
    queryFn: () => api.calculate(debouncedLoan),
    enabled: debouncedValid,
    placeholderData: (prev) => prev,
  });

  const create = useMutation({
    mutationFn: () => api.createDebt({ ...loan, name: name.trim() }, listId),
    onSuccess: (debt) => {
      queryClient.invalidateQueries({ queryKey: ["debts"] });
      navigate(`/debts/${debt.id}`, { replace: true });
    },
  });

  const onStartChange = (value: string) => {
    setStartDate(value);
    if (!firstPaymentTouched && value) setFirstPayment(addMonthsIso(value, 1));
  };

  const formError = !name.trim() ? "Введите название" : loanError;
  const rows = preview.data?.rows ?? [];
  const summary = preview.data?.summary;
  const payments = rows.map((r) => Number(r.payment));

  return (
    <div className="page">
      <BackButton to="/" />
      <header className="page-header">
        <h1>Новый долг</h1>
      </header>
      {targetList && !targetList.is_own && (
        <p className="hint">В список: {targetList.owner.display_name}</p>
      )}

      <section className="card form">
        <label className="field">
          <span>Название</span>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ипотека, автокредит…" maxLength={100} />
        </label>
        <label className="field">
          <span>Сумма долга, ₽</span>
          <input inputMode="decimal" value={principal} onChange={(e) => setPrincipal(e.target.value)} placeholder="1 000 000" />
        </label>
        <label className="field">
          <span>Ставка, % годовых</span>
          <input inputMode="decimal" value={rate} onChange={(e) => setRate(e.target.value)} placeholder="12,5" />
        </label>
        <label className="field">
          <span>Срок, месяцев</span>
          <input inputMode="numeric" value={term} onChange={(e) => setTerm(e.target.value.replace(/\D/g, ""))} />
        </label>
        <div className="chips">
          {TERM_PRESETS.map((m) => (
            <button key={m} className={`chip ${Number(term) === m ? "chip-on" : ""}`} onClick={() => setTerm(String(m))}>
              {m % 12 === 0 ? `${m / 12} г.` : pluralMonths(m)}
            </button>
          ))}
        </div>
        <div className="field-row">
          <label className="field">
            <span>Дата выдачи</span>
            <input type="date" value={startDate} onChange={(e) => onStartChange(e.target.value)} />
          </label>
          <label className="field">
            <span>Первый платёж</span>
            <input
              type="date"
              value={firstPayment}
              onChange={(e) => {
                setFirstPayment(e.target.value);
                setFirstPaymentTouched(true);
              }}
            />
          </label>
        </div>
        <div className="field">
          <span>Тип платежей</span>
          <div className="segmented">
            {(Object.keys(SCHEDULE_LABEL) as ScheduleType[]).map((t) => (
              <button key={t} className={scheduleType === t ? "segmented-on" : ""} onClick={() => setScheduleType(t)}>
                {SCHEDULE_LABEL[t]}
              </button>
            ))}
          </div>
        </div>
      </section>

      {summary && !loanError && (
        <section className="card preview">
          <div className="stat-grid">
            <div>
              <div className="hint">Ежемесячный платёж</div>
              <div className="stat-value">
                {scheduleType === "annuity"
                  ? money(payments[0])
                  : `${money(Math.max(...payments), true)} → ${money(Math.min(...payments), true)}`}
              </div>
            </div>
            <div>
              <div className="hint">Переплата</div>
              <div className="stat-value">{money(summary.total_interest)}</div>
            </div>
            <div>
              <div className="hint">Всего выплат</div>
              <div className="stat-value">{money(summary.total_payments)}</div>
            </div>
            <div>
              <div className="hint">Последний платёж</div>
              <div className="stat-value">{formatDate(summary.close_date)}</div>
            </div>
          </div>
          <button className="btn btn-plain btn-block" onClick={() => setShowSchedule((v) => !v)}>
            {showSchedule ? "Скрыть график" : "Показать график"}
          </button>
          {showSchedule && <ScheduleList rows={rows} />}
        </section>
      )}

      {create.error && <p className="error">{create.error.message}</p>}
      {formError && (name || principal || rate) && <p className="hint center-text">{formError}</p>}

      <MainButton
        text="Сохранить"
        onClick={() => !formError && create.mutate()}
        disabled={Boolean(formError)}
        loading={create.isPending}
      />
    </div>
  );
}
