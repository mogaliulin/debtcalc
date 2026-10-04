const moneyFormat = new Intl.NumberFormat("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const moneyShortFormat = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 });

export function money(value: string | number, short = false): string {
  const n = typeof value === "string" ? Number(value) : value;
  return `${(short ? moneyShortFormat : moneyFormat).format(n)} ₽`;
}

export function rate(value: string | number): string {
  return `${Number(value).toLocaleString("ru-RU", { maximumFractionDigits: 3 })}%`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-");
  return `${d}.${m}.${y}`;
}

export function todayIso(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

export function addMonthsIso(iso: string, months: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const target = new Date(y, m - 1 + months, 1);
  const lastDay = new Date(target.getFullYear(), target.getMonth() + 1, 0).getDate();
  target.setDate(Math.min(d, lastDay));
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${target.getFullYear()}-${pad(target.getMonth() + 1)}-${pad(target.getDate())}`;
}

export function pluralMonths(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return `${n} месяц`;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return `${n} месяца`;
  return `${n} месяцев`;
}

/** Нормализует ввод суммы: пробелы убираются, запятая → точка. */
export function normalizeNumber(input: string): string {
  return input.replace(/\s/g, "").replace(",", ".");
}

export const MODE_LABEL = {
  reduce_term: "уменьшение срока",
  reduce_payment: "уменьшение платежа",
} as const;

export const SCHEDULE_LABEL = {
  annuity: "Аннуитетный",
  differentiated: "Дифференцированный",
} as const;

export const ROLE_LABEL = {
  owner: "владелец",
  editor: "редактирование",
  viewer: "только просмотр",
} as const;

export const ROLE_DESC = {
  editor: "может добавлять и удалять долги, отмечать платежи и вносить досрочные погашения",
  viewer: "видит долги и графики, но ничего не меняет",
} as const;

/** Дата из ISO-строки с временем (например, срок действия приглашения). */
export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleDateString("ru-RU");
}
