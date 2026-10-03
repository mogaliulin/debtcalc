import { useQuery } from "@tanstack/react-query";
import { Navigate, Route, Routes } from "react-router-dom";
import { ApiError, api } from "./api/client";
import { DebtCreate } from "./pages/DebtCreate";
import { DebtDetail } from "./pages/DebtDetail";
import { DebtsList } from "./pages/DebtsList";
import { EarlyPaymentPage } from "./pages/EarlyPaymentPage";
import { Login } from "./pages/Login";
import { Settings } from "./pages/Settings";
import { ErrorState, Loading } from "./pages/states";

export function App() {
  const me = useQuery({ queryKey: ["me"], queryFn: api.me, staleTime: 5 * 60_000 });

  if (me.isPending) return <Loading />;

  const unauthorized = me.error instanceof ApiError && me.error.status === 401;
  if (unauthorized) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }
  if (me.error) return <ErrorState error={me.error} onRetry={me.refetch} />;

  return (
    <Routes>
      <Route path="/" element={<DebtsList me={me.data} />} />
      <Route path="/debts/new" element={<DebtCreate />} />
      <Route path="/debts/:id" element={<DebtDetail />} />
      <Route path="/debts/:id/early" element={<EarlyPaymentPage />} />
      <Route path="/settings" element={<Settings me={me.data} />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
