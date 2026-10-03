import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Me, MeUpdate } from "../api/types";
import { Avatar } from "../components/Avatar";
import { BackButton } from "../components/Buttons";
import { notify, useConfirm } from "../components/ConfirmDialog";

function timezones(current: string): string[] {
  const all = typeof Intl.supportedValuesOf === "function" ? Intl.supportedValuesOf("timeZone") : [];
  return all.includes(current) ? all : [current, ...all];
}

export function Settings({ me }: { me: Me }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const confirm = useConfirm();

  const update = useMutation({
    mutationFn: (data: MeUpdate) => api.updateMe(data),
    onSuccess: (data) => queryClient.setQueryData(["me"], data),
    onError: (e: Error) => notify(e.message),
  });
  const logout = useMutation({
    mutationFn: api.logout,
    onSuccess: () => {
      queryClient.clear();
      navigate("/login", { replace: true });
    },
    onError: (e: Error) => notify(e.message),
  });

  const zones = useMemo(() => timezones(me.timezone), [me.timezone]);
  const browserZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  return (
    <div className="page">
      <BackButton to="/" />
      <header className="page-header">
        <h1>Профиль</h1>
      </header>

      <section className="card profile">
        <Avatar me={me} size={56} />
        <div className="profile-text">
          <div className="profile-name">{me.display_name}</div>
          <div className="hint">{me.email ?? me.login}</div>
          <div className="hint">Вход через Яндекс ID</div>
        </div>
      </section>

      <h2 className="section-title">Настройки</h2>
      <section className="card form">
        <label className="field">
          <span>Часовой пояс</span>
          <select value={me.timezone} onChange={(e) => update.mutate({ timezone: e.target.value })}>
            {zones.map((z) => (
              <option key={z} value={z}>
                {z}
              </option>
            ))}
          </select>
        </label>
        {browserZone && browserZone !== me.timezone && (
          <button className="btn btn-plain" onClick={() => update.mutate({ timezone: browserZone })}>
            Использовать часовой пояс устройства ({browserZone})
          </button>
        )}
        <p className="hint">По часовому поясу определяется «сегодня» — какие платежи считаются просроченными.</p>
      </section>

      <button
        className="btn btn-danger-plain btn-block"
        disabled={logout.isPending}
        onClick={async () => {
          if (await confirm("Выйти из аккаунта?")) logout.mutate();
        }}
      >
        Выйти
      </button>
    </div>
  );
}
