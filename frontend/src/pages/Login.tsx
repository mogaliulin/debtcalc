import { useSearchParams } from "react-router-dom";
import { yandexLoginUrl } from "../api/client";

export function Login() {
  const [params] = useSearchParams();
  const error = params.get("error");
  const next = params.get("next");
  const invited = next?.startsWith("/invite/");

  return (
    <div className="page center login">
      <img className="login-logo" src="/favicon.svg" alt="" width={88} height={88} />
      <h1>Кредитный калькулятор</h1>
      <p className="hint login-text">
        Ведите свои кредиты и займы: график платежей, отметки об оплате и досрочные погашения в одном месте.
      </p>
      {invited && <p className="login-text">Войдите, чтобы принять приглашение в общий список долгов.</p>}
      {error && <p className="error">{error}</p>}
      {/* Обычная ссылка, а не fetch: сервер перенаправит браузер на oauth.yandex.ru */}
      <a className="btn btn-yandex" href={yandexLoginUrl(next)}>
        Войти с Яндекс ID
      </a>
    </div>
  );
}
