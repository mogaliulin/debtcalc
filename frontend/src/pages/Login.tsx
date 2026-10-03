import { useSearchParams } from "react-router-dom";
import { YANDEX_LOGIN_URL } from "../api/client";

export function Login() {
  const [params] = useSearchParams();
  const error = params.get("error");

  return (
    <div className="page center login">
      <img className="login-logo" src="/favicon.svg" alt="" width={88} height={88} />
      <h1>Кредитный калькулятор</h1>
      <p className="hint login-text">
        Ведите свои кредиты и займы: график платежей, отметки об оплате и досрочные погашения в одном месте.
      </p>
      {error && <p className="error">{error}</p>}
      {/* Обычная ссылка, а не fetch: сервер перенаправит браузер на oauth.yandex.ru */}
      <a className="btn btn-yandex" href={YANDEX_LOGIN_URL}>
        Войти с Яндекс ID
      </a>
    </div>
  );
}
