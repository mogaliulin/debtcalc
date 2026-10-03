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

## Развёртывание на сервере с HTTPS

Пример для домена `debtcalc.mogal.ru` и VPS на Ubuntu с Docker. Сертификат выпускает certbot на самом сервере,
nginx в контейнере `frontend` берёт его из `/etc/letsencrypt` (подключается файлом `docker-compose.prod.yml`).

1. **DNS.** В зоне `mogal.ru` — A-запись `debtcalc` → IP сервера.
2. **Код и настройки.**
   ```bash
   sudo git clone https://github.com/mogaliulin/debtcalc.git /opt/debtcalc && cd /opt/debtcalc
   sudo cp .env.example .env && sudo nano .env
   ```
   В `.env`: `DOMAIN=debtcalc.mogal.ru`, `PUBLIC_URL=https://debtcalc.mogal.ru`, ключи Яндекса,
   случайные `SECRET_KEY` и `POSTGRES_PASSWORD`, `DEV_AUTH_BYPASS=false`. Строку `HTTP_PORT` удалите
   (на сервере nginx слушает 80 и 443).
3. **Яндекс OAuth.** Добавьте Redirect URI `https://debtcalc.mogal.ru/api/auth/yandex/callback`.
4. **Сертификат.** Если certbot ещё не запускали:
   ```bash
   sudo certbot certonly --standalone -d debtcalc.mogal.ru   # порт 80 должен быть свободен
   ```
   Подойдёт и wildcard `*.mogal.ru`: тогда укажите в `.env` `CERT_NAME` — имя его папки в
   `/etc/letsencrypt/live/` (`sudo certbot certificates` → `Certificate Name`, обычно `mogal.ru`).
   Шаг 6 для wildcard не подходит: его продлевают только через DNS (см. ниже).
5. **Запуск.**
   ```bash
   sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
   ```
6. **Автопродление.** Сайт занимает порт 80, поэтому `--standalone` при продлении уже не сработает —
   переключите certbot на webroot (каталог `/var/www/certbot` смонтирован в nginx) и поставьте хук перезагрузки nginx:
   ```bash
   sudo mkdir -p /var/www/certbot
   sudo certbot certonly --webroot -w /var/www/certbot -d debtcalc.mogal.ru --force-renewal
   sudo install -m 755 deploy/certbot-reload-nginx.sh /etc/letsencrypt/renewal-hooks/deploy/reload-debtcalc.sh
   sudo certbot renew --dry-run                                # проверка, что продление работает
   ```
   Хук по умолчанию ищет проект в `/opt/debtcalc` (переменная `PROJECT_DIR` в скрипте).

   **Wildcard-сертификат** Let's Encrypt проверяет только по TXT-записи `_acme-challenge` в DNS. Если он выпущен
   вручную (`--manual`), сам он не продлится — раз в 90 дней придётся повторять выпуск и после него выполнять
   `docker compose -f docker-compose.yml -f docker-compose.prod.yml exec frontend nginx -s reload`.
   Для автопродления нужен DNS-плагин certbot для вашего DNS-провайдера с доступом к его API;
   хук из `deploy/` тоже установите — он перезагрузит nginx после продления.

Обновление после изменений в репозитории:
```bash
cd /opt/debtcalc && sudo git pull && sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Cookie получают флаг `Secure`, потому что `PUBLIC_URL` начинается с `https://`.
