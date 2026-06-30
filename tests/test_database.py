import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import Base, engine, SessionLocal
from database import models  # noqa: F401


def setup_module():
    Base.metadata.create_all(engine)


def test_create_content_node():
    session = SessionLocal()
    try:
        node = models.ContentNode(url="https://example.com/test", title="Test Page")
        session.add(node)
        session.commit()
        assert node.node_id is not None
    finally:
        session.query(models.ContentNode).filter_by(url="https://example.com/test").delete()
        session.commit()
        session.close()
