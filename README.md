# Botsad Backend — синхронизация конструкций (билбордов)

Бэкенд на FastAPI, который принимает события из Bitrix24, синхронизирует
конструкции (билборды) с PostgreSQL/PostGIS, кэширует их в RedisJSON,
раздаёт данные фронтенду, рассылает обновления по WebSocket и отправляет
исходящие вебхуки во внешнюю систему.

## Возможности

- приём входящих вебхуков Bitrix24 (`POST /api/webhook`) и синхронизация
  конструкций, локаций, размеров, материалов и районов;
- чтение баннеров из кэша RedisJSON (`GET /api/banners`,
  `GET /api/banners/{location_id}`);
- бронирование конструкции с записью в Bitrix24 (`POST /api/booking`);
- подсказки адресов (`GET /api/suggest/address`);
- живые обновления через WebSocket (`/ws/updates`) поверх Redis Pub/Sub;
- исходящие вебхуки о создании/обновлении/удалении конструкции;
- `/health` для проверок готовности и `/metrics` в формате Prometheus;
- приём бизнес-событий аналитики (`POST /analytics/events`);
- устойчивый старт: если Bitrix24 недоступен, API поднимается без полной
  синхронизации, а данные догружаются по входящим вебхукам.

## HTTP API

| Метод | Путь                     | Назначение                                   |
|-------|--------------------------|----------------------------------------------|
| GET   | `/health`                | Проверка готовности сервиса (204)            |
| POST  | `/api/webhook`           | Входящий вебхук Bitrix24                     |
| POST  | `/api/booking`           | Создание брони конструкции в Bitrix24        |
| GET   | `/api/banners`           | Список баннеров из кэша                      |
| GET   | `/api/banners/{location_id}` | Конструкции по локации                   |
| GET   | `/api/suggest/address`   | Подсказки адресов (DaData)                   |
| WS    | `/ws/updates`            | Подписка на обновления конструкций           |
| POST  | `/mock_ws`               | Ручная публикация сообщения в WS (для отладки) |
| POST  | `/analytics/events`      | Приём события аналитики                      |
| GET   | `/metrics`               | Метрики Prometheus                           |

Интерактивная документация — `/docs` (Swagger UI) и `/redoc`;
схема — `/openapi.json`.

## Исходящие вебхуки

Если задан `WEBHOOK_BASE_URL`, сервис отправляет события на
`<WEBHOOK_BASE_URL>/events` методом `POST`:

```json
{
  "type": "billboard.created | billboard.updated | billboard.deleted",
  "payload": {
    "billboard_id": 1,
    "location_id": 2,
    "crm_item_id": 123
  }
}
```

Успешным считается любой ответ `2xx` (обычно `204 No Content`).
Таймаут задаётся через `WEBHOOK_TIMEOUT`, повторные попытки — через
`WEBHOOK_RETRIES` и `WEBHOOK_BACKOFF_FACTOR`.
Ошибки отправки только логируются и не ломают обработку входящего события.
Если `WEBHOOK_BASE_URL` не задан, приложение стартует, а вебхуки не уходят.

## Требования

- Python 3.13;
- PostgreSQL с расширением PostGIS 16+;
- Redis Stack (RedisJSON + RediSearch + Pub/Sub);
- доступ к Bitrix24 REST, Яндекс.Геокодеру, S3 и DaData (по необходимости).

## Структура проекта

```
src/
  app.py                  # create_app(): middlewares, роутеры, lifespan
  main.py                 # точка входа uvicorn
  routers.py              # подключение всех роутеров
  middleware.py           # CORS, логирование запросов, /metrics
  exc_handler.py          # глобальные обработчики исключений
  billboards/             # чтение баннеров, группировка, сборка ответа
  crm/                    # вебхуки/брони, парсинг Bitrix24, синхронизация
  database/               # модели, схемы, репозитории, сессии SQLAlchemy
  external/               # Bitrix24, геокодер, S3, кэш, HTTP-клиенты, вебхуки
  geo/                    # подсказки адресов
  metrics/                # аналитика и сбор метрик
  mock/                   # отладочная ручка для WebSocket
  ws/                     # WebSocket-роут и рассылка через Redis Pub/Sub
  config/                 # настройки, логирование, трейсинг
tests/
  unit/                   # модульные тесты
  integrations/           # интеграционные тесты
```

## Конфигурация

Все настройки читаются из `.env` в корне проекта. За основу возьмите
`.env.example`:

```sh
cp .env.example .env
```

Ключевые группы переменных:

- `DB_*` — подключение к PostgreSQL (пароль, пул, SSL);
- `CACHE_*` / `BROADCAST_DB` — Redis-кэш и Pub/Sub;
- `BITRIX_*` — REST-вебхук Bitrix24 и параметры смарт-процесса;
- `YANDEX_GEOCODER_API_KEY`, `DISTRICTS_SERVICE_URL` — геокодирование;
- `S3_*`, `AWS_*` — хранение фотографий конструкций;
- `SUGGEST_API_KEY` — подсказки адресов DaData;
- `ANALYTICS_DB_*` — отдельная БД аналитики (опционально; без неё приём
  событий работает, но строки не сохраняются);
- `WEBHOOK_*` — исходящие вебхуки (опционально);
- `OTEL_*` — трассировка OpenTelemetry (по умолчанию выключена).

`.env` содержит секреты и не должен попадать в git.

## Локальный запуск

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env
python src/main.py
```

Сервис поднимется на `HOST:PORT` из `.env` (по умолчанию `0.0.0.0:8000`).

Для локального запуска укажите в `.env` доступные хосты:

- `DB_HOST=localhost` (или `127.0.0.1`);
- `CACHE_HOST=localhost`;
- при использовании `docker compose` для БД — `DB_PORT=55432`.

## Docker

`docker compose` поднимает backend, PostgreSQL/PostGIS и Redis Stack:

```sh
docker compose up -d --build
docker compose logs -f backend
docker compose down
```

- backend доступен на <http://localhost:9000> (внутри контейнера — порт 8000);
- PostgreSQL — на `localhost:55432`;
- Redis опубликованного порта не имеет и доступен только внутри сети compose.

В `.env` для этого режима укажите `DB_HOST=postgres` и `CACHE_HOST=redis`.

## Проверки качества

```sh
ruff check src
ruff format --check src
mypy src
pytest tests/unit
pytest
```

Все команды запускаются из корня проекта с активированным `.venv`
(в нём установлены `requirements-dev.txt`).

### Pre-commit

```sh
pre-commit install
pre-commit install --hook-type pre-push
pre-commit run --all-files
```

- на `git commit`: пробелы в конце строк, конец файла, YAML, большие файлы,
  конфликты слияния, `ruff` (с `--fix`) и `ruff format --check`;
- на `git push`: `mypy src` и `pytest tests/unit -q`.

Хуки mypy/pytest используют `language: system` и интерпретатор
`.venv/Scripts/python.exe` (Windows). Поэтому `.venv` должен находиться
именно в корне репозитория; на Linux/macOS путь в `.pre-commit-config.yaml`
нужно заменить на `.venv/bin/python`.

На Windows путь к интерпретатору в сгенерированных файлах `.git/hooks/*`
должен быть записан в UTF-8. Если `git commit` сообщает
`pre-commit not found`, переустановите хуки с включённым UTF-8:

```powershell
$env:PYTHONUTF8 = "1"
pre-commit install
pre-commit install --hook-type pre-push
Remove-Item Env:PYTHONUTF8
```

## Ограничения

- Kafka не используется: обмен событиями идёт через HTTP-вебхуки,
  Redis Pub/Sub и прямое чтение/запись БД;
- дедупликация входящих событий не реализована — повторный вебхук
  Bitrix24 приведёт к повторной синхронизации той же конструкции;
- сервис не является источником истины: данные приходят из Bitrix24,
  локальная БД и кэш — производные.
