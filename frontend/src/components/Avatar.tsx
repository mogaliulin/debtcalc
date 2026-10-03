import type { Me } from "../api/types";

export function Avatar({ me, size = 36 }: { me: Me; size?: number }) {
  const style = { width: size, height: size, fontSize: size * 0.42 };
  if (me.avatar_url) {
    return <img className="avatar" src={me.avatar_url} alt="" style={style} referrerPolicy="no-referrer" />;
  }
  const letter = (me.display_name || me.login || "?").trim().charAt(0).toUpperCase();
  return (
    <span className="avatar avatar-letter" style={style} aria-hidden>
      {letter}
    </span>
  );
}
