import type { Me } from "../api/types";

/** Подходит и для профиля (Me), и для владельца/участника списка (Person). */
type AvatarUser = Pick<Me, "display_name" | "login" | "avatar_url">;

export function Avatar({ user, size = 36 }: { user: AvatarUser; size?: number }) {
  const style = { width: size, height: size, fontSize: size * 0.42 };
  if (user.avatar_url) {
    return <img className="avatar" src={user.avatar_url} alt="" style={style} referrerPolicy="no-referrer" />;
  }
  const letter = (user.display_name || user.login || "?").trim().charAt(0).toUpperCase();
  return (
    <span className="avatar avatar-letter" style={style} aria-hidden>
      {letter}
    </span>
  );
}
