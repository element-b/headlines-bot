# Схема базы данных и инструкция по запуску

## Схема базы данных

Проект использует PostgreSQL.  
База данных хранит:

- источники новостей;
- заголовки новостей;
- пользователей Telegram;
- подписки пользователей на источники;
- историю уже отправленных заголовков.

---

## Таблица `sources`

Хранит список доступных новостных источников.

| Поле | Тип | Описание |
|---|---|---|
| `id` | `INTEGER` | Первичный ключ |
| `name` | `VARCHAR(100)` | Название источника |
| `slug` | `VARCHAR(50)` | Уникальный идентификатор источника |
| `url` | `VARCHAR(500)` | Базовый URL источника |
| `source_type` | `VARCHAR(20)` | Тип источника: `api` или `rss` |
| `is_active` | `BOOLEAN` | Активен ли источник |
| `created_at` | `TIMESTAMPTZ` | Время создания записи |

---

## Таблица `headlines`

Хранит новостные заголовки, полученные из источников.

| Поле | Тип | Описание |
|---|---|---|
| `id` | `INTEGER` | Первичный ключ |
| `source_id` | `INTEGER` | Ссылка на источник |
| `title` | `VARCHAR(500)` | Заголовок новости |
| `url` | `VARCHAR(1000)` | Ссылка на оригинальную новость |
| `published_at` | `TIMESTAMPTZ` | Время публикации у источника |
| `created_at` | `TIMESTAMPTZ` | Время сохранения в базе |

### Индексы
- `ix_headlines_source_published_at_desc` на поля `source_id`, `published_at`

### Особенности
- `url` уникален, что позволяет исключать дубликаты;
- пользователь получает новости по запросу именно из этой таблицы, а не напрямую из внешнего источника.

---

## Таблица `users`

Хранит пользователей Telegram-бота.

| Поле | Тип | Описание |
|---|---|---|
| `id` | `INTEGER` | Первичный ключ |
| `telegram_id` | `BIGINT` | Telegram ID пользователя |
| `username` | `VARCHAR(100)` | Username пользователя |
| `first_name` | `VARCHAR(100)` | Имя пользователя |
| `default_source_id` | `INTEGER` | Источник по умолчанию для команды `/news` |
| `headlines_count` | `INTEGER` | Количество заголовков в выдаче |
| `created_at` | `TIMESTAMPTZ` | Время создания |
| `updated_at` | `TIMESTAMPTZ` | Время обновления |

### Особенности
- `default_source_id` используется только для ручного запроса через `/news`;
- источник по умолчанию и подписки — разные сущности.

---

## Таблица `subscriptions`

Хранит подписки пользователей на новостные источники.

| Поле | Тип | Описание |
|---|---|---|
| `id` | `INTEGER` | Первичный ключ |
| `user_id` | `INTEGER` | Пользователь |
| `source_id` | `INTEGER` | Источник |
| `is_active` | `BOOLEAN` | Активна ли подписка |
| `created_at` | `TIMESTAMPTZ` | Время создания |

### Ограничения
- уникальная пара `user_id + source_id`

### Особенности
- подписка отвечает за автоматические уведомления;
- подписка не делает источник автоматически источником по умолчанию.

---

## Таблица `sent_headlines`

Хранит историю уже отправленных пользователю заголовков.

| Поле | Тип | Описание |
|---|---|---|
| `id` | `INTEGER` | Первичный ключ |
| `user_id` | `INTEGER` | Пользователь |
| `headline_id` | `INTEGER` | Заголовок |
| `sent_at` | `TIMESTAMPTZ` | Время отправки |

### Ограничения
- уникальная пара `user_id + headline_id`

### Особенности
- таблица используется для того, чтобы не отправлять пользователю одну и ту же новость повторно;
- после активации подписки уже существующие заголовки источника помечаются как отправленные, поэтому пользователь получает только новые новости.

---

## Логическая схема связей

```text
sources
  └──< headlines

users
  └──< subscriptions >── sources

users
  └──< sent_headlines >── headlines


Как создаётся схема БД

Для запуска через Docker Compose схема создаётся автоматически из файла:

docker/postgres/init.sql

Этот скрипт выполняется при первой инициализации пустого PostgreSQL volume.

Если volume уже существует, база не пересоздаётся, а данные сохраняются.
Используемые источники данных
API-источники

    The Guardian
    The New York Times

RSS-источники

    Коммерсантъ
    РБК

Почему англоязычные источники реализованы через API

Первоначально рассматривались Bloomberg и WSJ через HTML-скрапинг, но от этого решения было решено отказаться, поскольку:

    сайты активно защищены от ботов;
    часть контента рендерится динамически;
    возможны 403, paywall и нестабильная HTML-разметка;
    такой способ плохо подходит для надёжной реализации тестового задания.

Поэтому были выбраны более устойчивые источники с официальными API:

    The Guardian Open Platform API
    The New York Times Article Search API

Инструкция по запуску
Вариант 1. Полный запуск через Docker Compose
1. Клонировать репозиторий

git clone <repository_url>
cd headlines-bot

2. Создать файл .env

На основе .env.example создать файл .env и заполнить реальные значения:

BOT_TOKEN=your_telegram_bot_token

DATABASE_URL=postgresql+asyncpg://headlines:headlines@postgres:5432/headlines

SCRAPER_INTERVAL_SECONDS=240
NOTIFIER_INTERVAL_SECONDS=120
DEFAULT_HEADLINES_COUNT=5
HTTP_TIMEOUT_SECONDS=15
LOG_LEVEL=INFO

GUARDIAN_API_KEY=your_guardian_api_key
GUARDIAN_SECTIONS=business,world

NYTIMES_API_KEY=your_nytimes_api_key
NYTIMES_SECTIONS=business,world

3. Запустить проект

docker compose up --build

После запуска будут подняты:

    контейнер postgres;
    контейнер headlines-bot.

База данных создастся автоматически, после чего бот:

    заполнит таблицу sources значениями по умолчанию;
    начнёт polling Telegram;
    запустит фоновые сервисы сбора и рассылки новостей.

Вариант 2. Локальный запуск бота без Docker, но с PostgreSQL в Docker

Этот вариант использовался для разработки и отладки.
1. Поднять только PostgreSQL

docker compose up postgres -d

2. Изменить DATABASE_URL в .env

DATABASE_URL=postgresql+asyncpg://headlines:headlines@localhost:5432/headlines

3. Создать виртуальное окружение

python -m venv .venv

Linux / macOS:

source .venv/bin/activate

Windows PowerShell:

.venv\Scripts\Activate.ps1

4. Установить зависимости

pip install -r requirements.txt

5. Запустить приложение

python -m app

Проверка работы
Проверка контейнеров

docker compose ps

Просмотр логов

docker compose logs -f

Проверка активных источников

SELECT id, name, slug, url, source_type, is_active
FROM sources
ORDER BY id;

Ожидаемые активные источники:

    guardian
    nytimes
    kommersant
    rbc

Проверка сохранённых заголовков

SELECT
    h.id,
    s.slug,
    h.title,
    h.url,
    h.published_at,
    h.created_at
FROM headlines h
JOIN sources s ON s.id = h.source_id
ORDER BY COALESCE(h.published_at, h.created_at) DESC
LIMIT 20;

Проверка заголовков The Guardian

SELECT
    h.id,
    s.slug,
    h.title,
    h.url,
    h.published_at,
    h.created_at
FROM headlines h
JOIN sources s ON s.id = h.source_id
WHERE s.slug = 'guardian'
ORDER BY COALESCE(h.published_at, h.created_at) DESC
LIMIT 20;

Проверка заголовков The New York Times

SELECT
    h.id,
    s.slug,
    h.title,
    h.url,
    h.published_at,
    h.created_at
FROM headlines h
JOIN sources s ON s.id = h.source_id
WHERE s.slug = 'nytimes'
ORDER BY COALESCE(h.published_at, h.created_at) DESC
LIMIT 20;

Пользовательский сценарий
Получение новостей по запросу

    Пользователь запускает /start
    Открывает /settings
    Выбирает источник по умолчанию и количество заголовков
    Вызывает /news и получает последние новости из БД
    При необходимости вызывает /news_all и получает общую сводку

Работа с подписками

    Пользователь открывает /subscribe
    Выбирает один или несколько источников
    Получает только новые новости, появившиеся после подписки
    Смотрит активные подписки через /mysubs
    Отключает подписку через /unsubscribe

Особенности реализации
Новости по запросу берутся из базы данных

Это сделано специально:

    выдача пользователю не зависит от внешнего API в момент запроса;
    ответы работают быстрее;
    выполняется требование тестового задания: новости извлекаются из БД, а не загружаются заново с источника.

Подписка не отправляет старый архив

При активации подписки уже существующие новости выбранного источника помечаются как отправленные.
Это позволяет пользователю получать только новые заголовки, появившиеся после подписки.
Производительность

Для ускорения работы:

    используется локальный PostgreSQL в Docker Compose;
    уменьшено число лишних SQL round-trip;
    callback-запросы Telegram подтверждаются сразу;
    NotifierService ограничивает размер выборки и не загружает лишние данные.

Что можно улучшить дальше

    добавить автоматические тесты
    добавить мониторинг и healthchecks
    добавить более гибкую фильтрацию источников и секций
    реализовать административные команды
    при дальнейшем развитии проекта добавить полноценные миграции

Итог

Проект реализует:

    асинхронного Telegram-бота;
    сбор новостей из API и RSS;
    хранение данных в PostgreSQL;
    получение новостей по запросу;
    подписки на автоматическую рассылку;
    запуск через Docker Compose;
    структуру, удобную для дальнейшего расширения.
