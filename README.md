# Кредитный калькулятор

Веб-приложение для учёта своих долгов: пользователь добавляет и удаляет долги, смотрит график платежей
(аннуитетный или дифференцированный), отмечает платежи оплаченными, вносит досрочные платежи
(уменьшение срока или платежа) и удаляет ошибочные записи. Вход — через Яндекс ID.

- `backend/` — FastAPI + SQLAlchemy 2 (async) + Alembic + PostgreSQL
- `frontend/` — React + Vite + TypeScript, TanStack Query

## Как устроен расчёт

График не хранится в БД, а каждый раз вычисляется функцией `build_schedule`
([backend/app/services/calculator.py](backend/app/services/calculator.py)) из параметров долга и
досрочных платежей. Отметки «оплачено» хранятся по номеру периода. Поэтому удаление ошибочного досрочного
платежа — это удаление одной строки, после чего график пересчитывается.

- Проценты начисляются по дням: остаток × ставка × дни / 365 (366 в високосный год).
- Аннуитетный платёж считается по формуле с месячной ставкой (как в договоре), последний платёж
  корректирующий. При высокой ставке и коротком первом периоде долг может погаситься на несколько месяцев
  раньше срока договора — график показывает фактический срок.
- Досрочный платёж сначала гасит проценты, начисленные к его дате, остаток идёт в тело долга.
  Если дата совпадает с датой платежа, досрочный платёж применяется после регулярного.

## Вход через Яндекс ID

Используется OAuth 2.0 с кодом подтверждения и PKCE ([документация](https://yandex.ru/dev/id/doc/ru/codes/code-url)):

1. «Войти с Яндекс ID» ведёт на `/api/auth/yandex/login`. Сервер генерирует `state` и PKCE-пару, кладёт их
   в подписанную HttpOnly-cookie на 10 минут и перенаправляет на `oauth.yandex.ru/authorize`.
2. Яндекс возвращает пользователя на `/api/auth/yandex/callback?code=…&state=…`. Сервер сверяет `state`,
   меняет код на токен (`oauth.yandex.ru/token`), получает профиль (`login.yandex.ru/info`) и находит
   или создаёт пользователя по его Яндекс-`id`. Токен Яндекса не сохраняется.
3. Сервер создаёт сессию на 30 дней: в браузер уходит HttpOnly-cookie `session` (SameSite=Lax), в БД — только
   SHA-256 токена. Выход (`POST /api/auth/logout`) удаляет сессию.

### Регистрация приложения

1. Создайте приложение на https://oauth.yandex.ru/client/new, платформа «Веб-сервисы».
2. Доступы: логин, имя и фамилия, пол; адрес электронной почты; портрет пользователя.
3. Redirect URI: `{PUBLIC_URL}/api/auth/yandex/callback`, например
   `http://localhost:8080/api/auth/yandex/callback` для Docker и
   `http://localhost:5173/api/auth/yandex/callback` для `npm run dev`. Можно указать оба.
4. ClientID и Client secret запишите в `.env` (`YANDEX_CLIENT_ID`, `YANDEX_CLIENT_SECRET`).

## Локальная разработка (без Docker)

```bash
# backend
cd backend
py -3.13 -m venv .venv
.venv/Scripts/pip install -e ".[dev]"       # Linux/macOS: .venv/bin/pip
.venv/Scripts/pytest                         # тесты (SQLite, Postgres и Яндекс не нужны)

# API на SQLite; PUBLIC_URL указывает на dev-сервер фронтенда
export DATABASE_URL=sqlite+aiosqlite:///./dev.db PUBLIC_URL=http://localhost:5173
.venv/Scripts/alembic upgrade head
.venv/Scripts/uvicorn app.main:app --reload --port 8000

# frontend (в другом терминале), проксирует /api на :8000
cd frontend
npm install
npm run dev                                  # http://localhost:5173
```

Без настроенного приложения Яндекса можно временно включить `DEV_AUTH_BYPASS=true` —
API будет пускать без входа под тестовым пользователем. Не включайте это на публичном адресе.

Swagger: http://localhost:8000/api/docs

## Запуск в Docker

```bash
cp .env.example .env      # заполнить PUBLIC_URL, YANDEX_CLIENT_ID, YANDEX_CLIENT_SECRET, SECRET_KEY, POSTGRES_PASSWORD
docker compose up -d --build
```

Приложение будет на `http://localhost:${HTTP_PORT}` (nginx отдаёт фронтенд и проксирует `/api`).
Миграции применяются при старте контейнера `backend`.

На публичном сервере `PUBLIC_URL` должен быть `https://…` — тогда cookie получают флаг `Secure`.
