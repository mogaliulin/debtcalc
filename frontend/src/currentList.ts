import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "./api/client";
import type { DebtList } from "./api/types";

// Какой список долгов открыт на главной: свой или чужой, к которому открыт доступ. Хранится в браузере.
const STORAGE_KEY = "debtcalc.currentList";

function readStored(): number | null {
  try {
    const value = Number(localStorage.getItem(STORAGE_KEY));
    return Number.isInteger(value) && value > 0 ? value : null;
  } catch {
    return null;
  }
}

export function rememberList(ownerId: number): void {
  try {
    localStorage.setItem(STORAGE_KEY, String(ownerId));
  } catch {
    // приватный режим и т.п. — просто не запоминаем
  }
}

export function useLists() {
  return useQuery({ queryKey: ["lists"], queryFn: api.lists, staleTime: 60_000 });
}

export function useCurrentList() {
  const lists = useLists();
  const [stored, setStored] = useState(readStored);
  // если доступ к сохранённому списку отозвали — показываем свой
  const current: DebtList | undefined =
    lists.data?.find((l) => l.owner.user_id === stored) ?? lists.data?.find((l) => l.is_own);

  const select = (ownerId: number) => {
    rememberList(ownerId);
    setStored(ownerId);
  };
  return { lists, current, select };
}
