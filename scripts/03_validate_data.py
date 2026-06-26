"""Prints row counts for each table as a basic validation report."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import SessionLocal
from database.models import ContentNode, ContentEntity, RelationshipEdge, CrawlLog


def main():
    session = SessionLocal()
    try:
        print("=== KEN Interlinking Engine - Validation Report ===")
        print(f"content_nodes:      {session.query(ContentNode).count()}")
        print(f"content_entities:    {session.query(ContentEntity).count()}")
        print(f"relationship_edges:  {session.query(RelationshipEdge).count()}")
        print(f"crawl_logs:          {session.query(CrawlLog).count()}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
