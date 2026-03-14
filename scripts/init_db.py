"""
Применяет SQL миграции к БД.
Запускается автоматически при старте контейнера.
Idempotent — уже применённые миграции пропускаются через таблицу schema_migrations.
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

    # Таблица учёта применённых миграций
    cur.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename   VARCHAR(255) PRIMARY KEY,
            applied_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        cur.execute("SELECT 1 FROM schema_migrations WHERE filename = %s", (sql_file.name,))
        if cur.fetchone():
            print(f"  SKIP: {sql_file.name} (already applied)")
            continue

        print(f"Applying {sql_file.name}...")
        sql = sql_file.read_text()
        try:
            cur.execute(sql)
            cur.execute(
                "INSERT INTO schema_migrations (filename) VALUES (%s)",
                (sql_file.name,)
            )
            print(f"  OK: {sql_file.name}")
        except Exception as e:
            print(f"  ERROR in {sql_file.name}: {e}")
            raise

    cur.close()
    conn.close()
    print("DB initialization complete.")


if __name__ == "__main__":
    run()
