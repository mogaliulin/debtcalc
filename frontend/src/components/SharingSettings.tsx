import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { api } from "../api/client";
import type { Invite, MemberRole } from "../api/types";
import { useLists } from "../currentList";
import { ROLE_DESC, ROLE_LABEL, formatDateTime } from "../format";
import { Avatar } from "./Avatar";
import { notify, useConfirm } from "./ConfirmDialog";

const MEMBER_ROLES: MemberRole[] = ["editor", "viewer"];

function RoleSelect({ value, onChange, disabled }: { value: MemberRole; onChange: (r: MemberRole) => void; disabled?: boolean }) {
  return (
    <select
      className="role-select"
      value={value}
      disabled={disabled}
      aria-label="Права"
      onChange={(e) => onChange(e.target.value as MemberRole)}
    >
      {MEMBER_ROLES.map((r) => (
        <option key={r} value={r}>
          {ROLE_LABEL[r]}
        </option>
      ))}
    </select>
  );
}

function NewInviteLink({ invite }: { invite: Invite }) {
  const input = useRef<HTMLInputElement>(null);
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(invite.url!);
      setCopied(true);
    } catch {
      // буфер обмена недоступен (например, сайт открыт не по HTTPS) — выделяем ссылку для ручного копирования
      input.current?.select();
    }
  };

  return (
    <div className="invite-link">
      <div className="hint">
        Отправьте ссылку человеку, которому хотите открыть доступ ({ROLE_LABEL[invite.role]}). Она сработает один раз и
        действует до {formatDateTime(invite.expires_at)}. Позже эту ссылку посмотреть будет нельзя.
      </div>
      <div className="invite-link-row">
        <input ref={input} readOnly value={invite.url!} onFocus={(e) => e.target.select()} aria-label="Ссылка-приглашение" />
        <button className="btn btn-primary" onClick={copy}>
          {copied ? "Скопировано" : "Скопировать"}
        </button>
      </div>
    </div>
  );
}

/** Управление доступом к собственному списку и чужие списки, к которым есть доступ. */
export function SharingSettings() {
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const [inviteRole, setInviteRole] = useState<MemberRole>("editor");
  const [created, setCreated] = useState<Invite | null>(null);

  const members = useQuery({ queryKey: ["members"], queryFn: api.members });
  const invites = useQuery({ queryKey: ["invites"], queryFn: api.invites });
  const lists = useLists();
  const sharedWithMe = lists.data?.filter((l) => !l.is_own) ?? [];

  const refreshMembers = () => queryClient.invalidateQueries({ queryKey: ["members"] });
  const refreshInvites = () => queryClient.invalidateQueries({ queryKey: ["invites"] });
  const onError = (e: Error) => notify(e.message);

  const updateRole = useMutation({
    mutationFn: ({ userId, role }: { userId: number; role: MemberRole }) => api.updateMember(userId, role),
    onSuccess: refreshMembers,
    onError,
  });
  const removeMember = useMutation({ mutationFn: api.removeMember, onSuccess: refreshMembers, onError });
  const createInvite = useMutation({
    mutationFn: () => api.createInvite(inviteRole),
    onSuccess: (invite) => {
      setCreated(invite);
      refreshInvites();
    },
    onError,
  });
  const revokeInvite = useMutation({
    mutationFn: api.revokeInvite,
    onSuccess: (_, id) => {
      if (created?.id === id) setCreated(null);
      refreshInvites();
    },
    onError,
  });
  const leave = useMutation({
    mutationFn: api.leaveList,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["lists"] }),
    onError,
  });

  return (
    <>
      <h2 className="section-title">Совместный доступ к моему списку</h2>
      <section className="card form">
        {members.data?.length ? (
          <ul className="people">
            {members.data.map((m) => (
              <li key={m.user.user_id} className="person-row">
                <Avatar user={m.user} size={36} />
                <div className="person-text">
                  <div className="person-name">{m.user.display_name}</div>
                  <div className="hint">{m.user.login}</div>
                </div>
                <RoleSelect
                  value={m.role}
                  disabled={updateRole.isPending}
                  onChange={(role) => updateRole.mutate({ userId: m.user.user_id, role })}
                />
                <button
                  className="icon-btn icon-btn-danger"
                  aria-label={`Закрыть доступ для ${m.user.display_name}`}
                  disabled={removeMember.isPending}
                  onClick={async () => {
                    if (await confirm(`Закрыть доступ к вашему списку для ${m.user.display_name}?`)) {
                      removeMember.mutate(m.user.user_id);
                    }
                  }}
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="hint">{members.isPending ? "Загрузка…" : "Пока доступ есть только у вас."}</p>
        )}

        <div className="field">
          <span>Пригласить с правами</span>
          <div className="segmented">
            {MEMBER_ROLES.map((r) => (
              <button key={r} className={inviteRole === r ? "segmented-on" : ""} onClick={() => setInviteRole(r)}>
                {ROLE_LABEL[r]}
              </button>
            ))}
          </div>
          <span className="hint">Участник {ROLE_DESC[inviteRole]}.</span>
        </div>
        <button className="btn btn-plain" disabled={createInvite.isPending} onClick={() => createInvite.mutate()}>
          {createInvite.isPending ? "Создаём…" : "Создать ссылку-приглашение"}
        </button>
        {created && <NewInviteLink invite={created} />}

        {invites.data && invites.data.length > 0 && (
          <div className="field">
            <span>Активные приглашения</span>
            <ul className="people">
              {invites.data.map((i) => (
                <li key={i.id} className="person-row">
                  <div className="person-text">
                    <div>{ROLE_LABEL[i.role]}</div>
                    <div className="hint">до {formatDateTime(i.expires_at)}</div>
                  </div>
                  <button
                    className="btn btn-danger-plain"
                    disabled={revokeInvite.isPending}
                    onClick={() => revokeInvite.mutate(i.id)}
                  >
                    Отозвать
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      {sharedWithMe.length > 0 && (
        <>
          <h2 className="section-title">Списки, к которым у меня есть доступ</h2>
          <section className="card">
            <ul className="people">
              {sharedWithMe.map((l) => (
                <li key={l.owner.user_id} className="person-row">
                  <Avatar user={l.owner} size={36} />
                  <div className="person-text">
                    <div className="person-name">{l.owner.display_name}</div>
                    <div className="hint">{ROLE_LABEL[l.role]}</div>
                  </div>
                  <button
                    className="btn btn-danger-plain"
                    disabled={leave.isPending}
                    onClick={async () => {
                      if (await confirm(`Выйти из списка ${l.owner.display_name}? Вернуться можно будет только по новому приглашению.`)) {
                        leave.mutate(l.owner.user_id);
                      }
                    }}
                  >
                    Выйти
                  </button>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </>
  );
}
