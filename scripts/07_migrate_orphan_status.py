"""Migrate content_nodes.orphan_status from INTEGER affinity to VARCHAR.

SQLite allows text in INTEGER-affinity columns, but Agent 1 uses explicit
categorical values. This transactional migration aligns the physical schema
with the SQLAlchemy model and documentation while preserving all rows/indexes.
"""

import argparse
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def migrate(db_path: Path) -> bool:
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        declared = conn.execute(
            "SELECT type FROM pragma_table_info('content_nodes') WHERE name='orphan_status'"
        ).fetchone()
        if not declared:
            raise RuntimeError("content_nodes.orphan_status does not exist")
        if declared[0].upper() in {"VARCHAR", "TEXT"}:
            print(f"Already migrated: orphan_status {declared[0]}")
            return False

        table_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='content_nodes'"
        ).fetchone()[0]
        indexes = [
            row[0]
            for row in conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='index' "
                "AND tbl_name='content_nodes' AND sql IS NOT NULL"
            )
        ]
        columns = [
            row[1] for row in conn.execute("PRAGMA table_info(content_nodes)")
        ]
        new_sql = table_sql.replace(
            "CREATE TABLE content_nodes", "CREATE TABLE content_nodes_new", 1
        )
        new_sql = new_sql.replace("orphan_status INTEGER", "orphan_status VARCHAR", 1)
        if new_sql == table_sql:
            raise RuntimeError("Could not construct VARCHAR migration SQL")

        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(new_sql)
        names = ",".join(f'"{name}"' for name in columns)
        conn.execute(
            f"INSERT INTO content_nodes_new ({names}) SELECT {names} FROM content_nodes"
        )
        conn.execute("DROP TABLE content_nodes")
        conn.execute("ALTER TABLE content_nodes_new RENAME TO content_nodes")
        for index_sql in indexes:
            conn.execute(index_sql)
        conn.commit()
        conn.execute("PRAGMA foreign_keys=ON")
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_key_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
        if integrity != "ok" or foreign_key_errors:
            raise RuntimeError(
                f"Post-migration validation failed: integrity={integrity}, "
                f"foreign_keys={foreign_key_errors[:5]}"
            )
        print("Migrated orphan_status: INTEGER -> VARCHAR")
        print(f"Rows preserved: {conn.execute('SELECT COUNT(*) FROM content_nodes').fetchone()[0]}")
        print("Integrity: ok")
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "ken_links.db"))
    args = parser.parse_args()
    migrate(Path(args.db))


if __name__ == "__main__":
    main()
