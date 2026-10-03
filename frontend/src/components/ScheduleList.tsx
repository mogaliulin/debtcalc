import type { ScheduleRow } from "../api/types";
import { MODE_LABEL, formatDate, money } from "../format";

interface Props {
  rows: ScheduleRow[];
  /** Без обработчиков список только для просмотра (предпросмотр при создании). */
  onTogglePaid?: (row: ScheduleRow) => void;
  onDeleteEarly?: (row: ScheduleRow) => void;
  busyKey?: string | null;
}

export function rowKey(row: ScheduleRow): string {
  return row.kind === "early" ? `e${row.early_payment_id}` : `p${row.period_no}`;
}

export function ScheduleList({ rows, onTogglePaid, onDeleteEarly, busyKey }: Props) {
  return (
    <ul className="schedule">
      {rows.map((row) => {
        const key = rowKey(row);
        const busy = busyKey === key;
        if (row.kind === "early") {
          return (
            <li key={key} className="schedule-row schedule-row-early">
              <span className="schedule-icon" aria-hidden>
                ⚡
              </span>
              <div className="schedule-main">
                <div className="schedule-top">
                  <span>Досрочно · {row.early_mode ? MODE_LABEL[row.early_mode] : ""}</span>
                  <span>{formatDate(row.date)}</span>
                </div>
                <div className="schedule-amount">{money(row.payment)}</div>
                <div className="schedule-sub">
                  Осн. долг {money(row.principal, true)}
                  {Number(row.interest) > 0 && <> · % {money(row.interest, true)}</>} · Остаток{" "}
                  {money(row.balance_after, true)}
                </div>
              </div>
              {onDeleteEarly && (
                <button
                  className="icon-btn icon-btn-danger"
                  aria-label="Удалить досрочный платёж"
                  disabled={busy}
                  onClick={() => onDeleteEarly(row)}
                >
                  ✕
                </button>
              )}
            </li>
          );
        }
        const status = row.is_paid ? "paid" : row.is_overdue ? "overdue" : "open";
        return (
          <li key={key} className={`schedule-row schedule-row-${status}`}>
            {onTogglePaid ? (
              <button
                className={`check ${row.is_paid ? "check-on" : ""}`}
                aria-label={row.is_paid ? "Снять отметку об оплате" : "Отметить оплаченным"}
                aria-pressed={row.is_paid}
                disabled={busy}
                onClick={() => onTogglePaid(row)}
              >
                {row.is_paid ? "✓" : ""}
              </button>
            ) : (
              <span className="schedule-no">{row.period_no}</span>
            )}
            <div className="schedule-main">
              <div className="schedule-top">
                <span>
                  №{row.period_no}
                  {status === "overdue" && <span className="overdue-label"> · просрочен</span>}
                </span>
                <span>{formatDate(row.date)}</span>
              </div>
              <div className="schedule-amount">{money(row.payment)}</div>
              <div className="schedule-sub">
                Осн. долг {money(row.principal, true)} · % {money(row.interest, true)} · Остаток{" "}
                {money(row.balance_after, true)}
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
