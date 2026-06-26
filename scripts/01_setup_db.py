"""Creates ken_links.db with all Phase 1 tables."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import Base, engine
from database import models  # noqa: F401  (registers models with Base)


def main():
    Base.metadata.create_all(engine)
    tables = list(Base.metadata.tables.keys())
    print(f"Database ready with {len(tables)} tables: {', '.join(tables)}")


if __name__ == "__main__":
    main()
