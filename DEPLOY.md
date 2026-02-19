# Деплой на Railway

## 1. Подготовка GitHub репозитория

```bash
cd /home/nalivator3000/Claude/vladtrans
git init
git add .
git commit -m "initial commit"
# Создать репо на github.com, затем:
git remote add origin https://github.com/ВАШ_НИК/vladtrans.git
git push -u origin main
```

> Убедись что `.env` есть в `.gitignore` — секреты не должны попасть в репо.

---

## 2. Создание проекта на Railway

1. Открыть [railway.app](https://railway.app) → **New Project**
2. Выбрать **Deploy from GitHub repo**
3. Выбрать репозиторий `vladtrans`
4. Railway автоматически найдёт `Dockerfile` — нажать **Deploy**

---

## 3. Добавить плагины

В проекте на Railway нажать **+ New** для каждого:

### PostgreSQL
- **+ New** → **Database** → **Add PostgreSQL**
- После создания Railway автоматически добавит `DATABASE_URL` в env всех сервисов проекта

### Redis
- **+ New** → **Database** → **Add Redis**
- Railway автоматически добавит `REDIS_URL`

---

## 4. Переменные окружения

### Сервис: `api` (основной)

В Railway → выбрать сервис → **Variables** → добавить вручную:

| Переменная | Значение |
|---|---|
| `OPENAI_API_KEY` | `sk-proj-...` |

Следующие переменные Railway **проставляет автоматически** из плагинов:

| Переменная | Источник |
|---|---|
| `DATABASE_URL` | PostgreSQL плагин |
| `REDIS_URL` | Redis плагин |
| `PORT` | Railway (автоматически) |

### Сервис: `worker` (Celery)

- **+ New** → **Empty Service**
- Source: тот же GitHub репозиторий
- **Settings** → **Start Command**:
  ```
  celery -A app.core.celery_app worker --loglevel=info --concurrency=4
  ```
- **Variables**: добавить те же переменные что у `api`:

| Переменная | Значение |
|---|---|
| `OPENAI_API_KEY` | `sk-proj-...` |
| `DATABASE_URL` | скопировать из сервиса `api` (ссылка на PostgreSQL плагин) |
| `REDIS_URL` | скопировать из сервиса `api` (ссылка на Redis плагин) |

> Или использовать **Shared Variables** — Railway позволяет расшарить переменные между сервисами одного проекта.

---

## 5. БД инициализируется автоматически

При каждом старте контейнер выполняет:
```
python scripts/init_db.py && uvicorn ...
```

Скрипт применяет `migrations/001_init.sql`. Повторные запуски безопасны — если таблицы уже существуют, шаг пропускается.

Проверить что всё применилось можно через Railway → PostgreSQL → **Query**:
```sql
\dt
SELECT * FROM operators LIMIT 1;
```

---

## 6. Проверка деплоя

После деплоя открыть URL сервиса (Railway показывает в Dashboard):

```
GET https://vladtrans-api-xxx.railway.app/health
→ {"status": "ok"}

GET https://vladtrans-api-xxx.railway.app/docs
→ Swagger UI со всеми эндпоинтами
```

---

## Структура сервисов в Railway

```
Railway Project: vladtrans
├── api         (FastAPI, Dockerfile, порт $PORT)
├── worker      (Celery, тот же Dockerfile, кастомный start command)
├── PostgreSQL  (плагин, даёт DATABASE_URL)
└── Redis       (плагин, даёт REDIS_URL)
```
