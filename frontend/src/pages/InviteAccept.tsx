import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, api } from "../api/client";
import { Avatar } from "../components/Avatar";
import { MainButton } from "../components/Buttons";
import { rememberList } from "../currentList";
import { ROLE_DESC, ROLE_LABEL } from "../format";
import { ErrorState, Loading } from "./states";

export function InviteAccept() {
  const token = useParams().token ?? "";
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const preview = useQuery({ queryKey: ["invite", token], queryFn: () => api.previewInvite(token), retry: false });

  const openList = (ownerId: number) => {
    rememberList(ownerId);
    navigate("/", { replace: true });
  };

  const accept = useMutation({
    mutationFn: () => api.acceptInvite(token),
    onSuccess: async (list) => {
      queryClient.removeQueries({ queryKey: ["invite", token] });
      await queryClient.invalidateQueries({ queryKey: ["lists"] });
      openList(list.owner.user_id);
    },
  });

  if (preview.isPending) return <Loading />;
  if (preview.error) {
    if (preview.error instanceof ApiError && preview.error.status === 404) {
      return (
        <div className="page center">
          <p>Приглашение не найдено или устарело.</p>
          <p className="hint">Попросите владельца списка прислать новую ссылку.</p>
          <Link className="btn btn-plain" to="/">
            На главную
          </Link>
        </div>
      );
    }
    return <ErrorState error={preview.error} onRetry={preview.refetch} />;
  }

  const { owner, role, is_own, current_role } = preview.data;

  if (is_own) {
    return (
      <div className="page center">
        <p>Это приглашение в ваш собственный список.</p>
        <p className="hint">Отправьте ссылку человеку, которому хотите открыть доступ.</p>
        <Link className="btn btn-plain" to="/settings">
          К настройкам доступа
        </Link>
      </div>
    );
  }

  const sameRole = current_role === role;

  return (
    <div className="page center invite">
      <Avatar user={owner} size={72} />
      <h1>{owner.display_name}</h1>
      <p>приглашает вас в свой список долгов</p>
      <p className="hint">
        Права: <b>{ROLE_LABEL[role]}</b> — вы {ROLE_DESC[role]}.
      </p>
      {current_role && (
        <p className="hint">
          {sameRole
            ? "У вас уже есть такой доступ к этому списку."
            : `Сейчас у вас ${ROLE_LABEL[current_role]} — после принятия будет ${ROLE_LABEL[role]}.`}
        </p>
      )}
      {accept.error && <p className="error">{accept.error.message}</p>}
      {sameRole ? (
        <MainButton text="Открыть список" onClick={() => openList(owner.user_id)} />
      ) : (
        <MainButton text="Принять приглашение" onClick={() => accept.mutate()} loading={accept.isPending} />
      )}
    </div>
  );
}
