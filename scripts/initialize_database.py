from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = REPO_ROOT / "db" / "schema.sql"
DEFAULT_DATABASE = REPO_ROOT / "data" / "tender-agent.sqlite"


def initialize_database(database_path: Path, schema_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    schema_sql = schema_path.read_text(encoding="utf-8")
    with sqlite3.connect(database_path) as connection:
        connection.executescript(schema_sql)
        connection.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize the Tender Agent SQLite database.")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    args = parser.parse_args()

    initialize_database(args.database, args.schema)
    print(f"Initialized SQLite database: {args.database}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
