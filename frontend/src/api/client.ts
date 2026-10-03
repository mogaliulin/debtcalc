import type { Debt, DebtInput, EarlyPaymentInput, LoanInput, Me, MeUpdate, Schedule } from "./types";

const BASE = import.meta.env.VITE_API_URL ?? "";

/** Полная навигация (не fetch): сервер перенаправит на страницу входа Яндекс ID. */
export const YANDEX_LOGIN_URL = `${BASE}/api/auth/yandex/login`;

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

function errorMessage(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const msg = String((detail[0] as { msg?: string }).msg ?? "");
    return msg.replace(/^Value error,\s*/, "") || "Проверьте введённые данные";
  }
  return `Ошибка сервера (${status})`;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let response: Response;
  try {
    response = await fetch(`${BASE}/api${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: "same-origin",
    });
  } catch {
    throw new ApiError("Нет связи с сервером", 0);
  }
  if (response.status === 204) return undefined as T;
  const payload = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(errorMessage(payload, response.status), response.status);
  return payload as T;
}

export const api = {
  me: () => request<Me>("GET", "/me"),
  updateMe: (data: MeUpdate) => request<Me>("PATCH", "/me", data),
  logout: () => request<void>("POST", "/auth/logout"),

  calculate: (loan: LoanInput) => request<Schedule>("POST", "/calculate", loan),

  debts: () => request<Debt[]>("GET", "/debts"),
  debt: (id: number) => request<Debt>("GET", `/debts/${id}`),
  createDebt: (data: DebtInput) => request<Debt>("POST", "/debts", data),
  renameDebt: (id: number, name: string) => request<Debt>("PATCH", `/debts/${id}`, { name }),
  deleteDebt: (id: number) => request<void>("DELETE", `/debts/${id}`),

  schedule: (id: number) => request<Schedule>("GET", `/debts/${id}/schedule`),
  setPaid: (id: number, period: number, paid: boolean) =>
    request<Schedule>(paid ? "PUT" : "DELETE", `/debts/${id}/periods/${period}/paid`),
  addEarlyPayment: (id: number, data: EarlyPaymentInput) =>
    request<Schedule>("POST", `/debts/${id}/early-payments`, data),
  deleteEarlyPayment: (id: number, earlyId: number) =>
    request<Schedule>("DELETE", `/debts/${id}/early-payments/${earlyId}`),
};
