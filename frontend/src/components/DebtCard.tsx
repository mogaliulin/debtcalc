import { Link } from "react-router-dom";
import type { Debt } from "../api/types";
import { formatDate, money, rate } from "../format";
import { ProgressBar } from "./ProgressBar";

export function DebtCard({ debt }: { debt: Debt }) {
  const { summary } = debt;
  const next = summary.next_payment;
  return (
    <Link to={`/debts/${debt.id}`} className="card debt-card">
      <div className="debt-card-head">
        <span className="debt-card-name">{debt.name}</span>
        {summary.overdue_count > 0 && <span className="badge badge-danger">просрочено: {summary.overdue_count}</span>}
        {summary.is_closed && <span className="badge badge-success">погашен</span>}
      </div>
      <div className="debt-card-balance">{money(summary.remaining_balance)}</div>
      <ProgressBar value={summary.progress} />
      <div className="debt-card-foot">
        {next ? (
          <span>
            След. платёж <b>{money(next.payment)}</b> · {formatDate(next.date)}
          </span>
        ) : (
          <span>Все платежи внесены</span>
        )}
        <span className="hint">{rate(debt.annual_rate)}</span>
      </div>
    </Link>
  );
}
