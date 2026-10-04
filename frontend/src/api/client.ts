import type {
  Debt,
  DebtInput,
  DebtList,
  EarlyPaymentInput,
  Invite,
  InvitePreview,
  LoanInput,
  Me,
  MeUpdate,
  Member,
  MemberRole,
  Schedule,
} from "./types";

const BASE = import.meta.env.VITE_API_URL ?? "";

/**
 * Адрес для полной навигации (не fetch): сервер перенаправит на страницу входа Яндекс ID,
 * а после входа вернёт на next (только внутренний путь — сервер проверяет это сам).
 */
export function yandexLoginUrl(next?: string | null): string {
  const query = next && next !== "/" ? `?${new URLSearchParams({ next })}` : "";
  return `${BASE}/api/auth/yandex/login${query}`;
}

const listQuery = (listId?: number) => (listId === undefined ? "" : `?list_id=${listId}`);

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

  /** listId — id владельца списка; без него — собственный список. */
  debts: (listId?: number) => request<Debt[]>("GET", `/debts${listQuery(listId)}`),
  debt: (id: number) => request<Debt>("GET", `/debts/${id}`),
  createDebt: (data: DebtInput, listId?: number) => request<Debt>("POST", `/debts${listQuery(listId)}`, data),
  renameDebt: (id: number, name: string) => request<Debt>("PATCH", `/debts/${id}`, { name }),
  deleteDebt: (id: number) => request<void>("DELETE", `/debts/${id}`),

  schedule: (id: number) => request<Schedule>("GET", `/debts/${id}/schedule`),
  setPaid: (id: number, period: number, paid: boolean) =>
    request<Schedule>(paid ? "PUT" : "DELETE", `/debts/${id}/periods/${period}/paid`),
  addEarlyPayment: (id: number, data: EarlyPaymentInput) =>
    request<Schedule>("POST", `/debts/${id}/early-payments`, data),
  deleteEarlyPayment: (id: number, earlyId: number) =>
    request<Schedule>("DELETE", `/debts/${id}/early-payments/${earlyId}`),

  lists: () => request<DebtList[]>("GET", "/lists"),
  leaveList: (ownerId: number) => request<void>("DELETE", `/lists/${ownerId}/membership`),

  members: () => request<Member[]>("GET", "/sharing/members"),
  updateMember: (userId: number, role: MemberRole) => request<Member>("PATCH", `/sharing/members/${userId}`, { role }),
  removeMember: (userId: number) => request<void>("DELETE", `/sharing/members/${userId}`),
  invites: () => request<Invite[]>("GET", "/sharing/invites"),
  createInvite: (role: MemberRole) => request<Invite>("POST", "/sharing/invites", { role }),
  revokeInvite: (id: number) => request<void>("DELETE", `/sharing/invites/${id}`),
  previewInvite: (token: string) => request<InvitePreview>("GET", `/invites/${encodeURIComponent(token)}`),
  acceptInvite: (token: string) => request<DebtList>("POST", `/invites/${encodeURIComponent(token)}/accept`),
};
