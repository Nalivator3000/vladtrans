"""
Применяет SQL миграции к БД.
Запускается автоматически при старте контейнера.
Idempotent — повторный запуск не сломает уже существующие таблицы.
"""
import sys
import psycopg2
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def run():
    conn = psycopg2.connect(settings.sync_database_url)
    conn.autocommit = True
    cur = conn.cursor()

    for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        print(f"Applying {sql_file.name}...")
        sql = sql_file.read_text()
        try:
            cur.execute(sql)
            print(f"  OK: {sql_file.name}")
        except psycopg2.errors.DuplicateTable:
            print(f"  SKIP: {sql_file.name} (tables already exist)")
        except Exception as e:
            print(f"  ERROR in {sql_file.name}: {e}")
            raise

    cur.close()
    conn.close()
    print("DB initialization complete.")


if __name__ == "__main__":
    run()
