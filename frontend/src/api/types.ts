// Денежные значения приходят строками (Decimal) — переводим в число только для отображения.

export type ScheduleType = "annuity" | "differentiated";
export type EarlyMode = "reduce_term" | "reduce_payment";
/** Права текущего пользователя на список долгов. */
export type Role = "owner" | "editor" | "viewer";
export type MemberRole = Exclude<Role, "owner">;

export interface LoanInput {
  principal: string;
  annual_rate: string;
  term_months: number;
  start_date: string;
  first_payment_date: string;
  schedule_type: ScheduleType;
}

export interface DebtInput extends LoanInput {
  name: string;
}

export interface ScheduleRow {
  period_no: number | null;
  date: string;
  kind: "regular" | "early";
  payment: string;
  interest: string;
  principal: string;
  balance_after: string;
  is_paid: boolean;
  is_overdue: boolean;
  early_payment_id: number | null;
  early_mode: EarlyMode | null;
}

export interface Summary {
  principal: string;
  remaining_balance: string;
  total_payments: string;
  total_interest: string;
  close_date: string | null;
  periods_count: number;
  paid_count: number;
  overdue_count: number;
  next_payment: ScheduleRow | null;
  progress: number;
  is_closed: boolean;
}

export interface EarlyPayment {
  id: number;
  date: string;
  amount: string;
  mode: EarlyMode;
}

export interface Debt {
  id: number;
  name: string;
  principal: string;
  annual_rate: string;
  term_months: number;
  start_date: string;
  first_payment_date: string;
  schedule_type: ScheduleType;
  early_payments: EarlyPayment[];
  summary: Summary;
  owner_id: number;
  role: Role;
}

export interface Schedule {
  rows: ScheduleRow[];
  summary: Summary;
}

export interface EarlyPaymentInput {
  date: string;
  amount: string;
  mode: EarlyMode;
}

export interface Me {
  id: number;
  login: string;
  display_name: string;
  email: string | null;
  avatar_url: string | null;
  timezone: string;
}

export type MeUpdate = Partial<Pick<Me, "timezone">>;

export interface Person {
  user_id: number;
  display_name: string;
  login: string;
  avatar_url: string | null;
}

/** Список долгов (все долги владельца), доступный текущему пользователю. */
export interface DebtList {
  owner: Person;
  role: Role;
  is_own: boolean;
}

export interface Member {
  user: Person;
  role: MemberRole;
}

export interface Invite {
  id: number;
  role: MemberRole;
  expires_at: string;
  /** Только в ответе на создание: сервер хранит лишь хэш токена. */
  url: string | null;
}

export interface InvitePreview {
  owner: Person;
  role: MemberRole;
  is_own: boolean;
  current_role: Role | null;
}
