"""
KEN Interlinking Engine - Phase 1 Setup
Creates project folder structure and starter files.
"""
import os

ROOT = os.path.dirname(os.path.abspath(__file__))

FILES = {
    "config/__init__.py": "",
    "config/settings.py": '''import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///ken_links.db")
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
''',

    "database/__init__.py": "",
    "database/db.py": '''from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from config.settings import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
''',

    "database/models.py": '''from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from database.db import Base


class ContentNode(Base):
    __tablename__ = "content_nodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String, unique=True, nullable=False)
    title = Column(String)
    content_type = Column(String)
    word_count = Column(Integer, default=0)
    published_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    entities = relationship("ContentEntity", back_populates="content_node")


class ContentEntity(Base):
    __tablename__ = "content_entities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_node_id = Column(Integer, ForeignKey("content_nodes.id"), nullable=False)
    entity_text = Column(String, nullable=False)
    entity_type = Column(String)
    confidence_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    content_node = relationship("ContentNode", back_populates="entities")


class RelationshipEdge(Base):
    __tablename__ = "relationship_edges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_node_id = Column(Integer, ForeignKey("content_nodes.id"), nullable=False)
    target_node_id = Column(Integer, ForeignKey("content_nodes.id"), nullable=False)
    relationship_type = Column(String)
    anchor_text = Column(String)
    weight = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)


class CrawlLog(Base):
    __tablename__ = "crawl_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String, nullable=False)
    status = Column(String)
    error_message = Column(Text)
    crawled_at = Column(DateTime, default=datetime.utcnow)
''',

    "api/__init__.py": "",
    "api/main.py": '''from fastapi import FastAPI

from config.settings import API_HOST, API_PORT

app = FastAPI(title="KEN Interlinking Engine")


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.main:app", host=API_HOST, port=API_PORT, reload=True)
''',

    "scripts/__init__.py": "",
    "scripts/01_setup_db.py": '''"""Creates ken_links.db with all Phase 1 tables."""
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
''',

    "scripts/03_validate_data.py": '''"""Prints row counts for each table as a basic validation report."""
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
''',

    "tests/__init__.py": "",
    "tests/test_database.py": '''import sys
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
        assert node.id is not None
    finally:
        session.query(models.ContentNode).filter_by(url="https://example.com/test").delete()
        session.commit()
        session.close()
''',

    "data/.gitkeep": "",

    "requirements.txt": '''fastapi
uvicorn
sqlalchemy
python-dotenv
pydantic
pytest
''',

    ".env.example": '''DATABASE_URL=sqlite:///ken_links.db
API_HOST=0.0.0.0
API_PORT=8000
''',

    ".gitignore": '''venv/
__pycache__/
*.pyc
.env
*.db
''',
}


def main():
    for rel_path, content in FILES.items():
        full_path = os.path.join(ROOT, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        if not os.path.exists(full_path):
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Created: {rel_path}")
        else:
            print(f"Skipped (exists): {rel_path}")


if __name__ == "__main__":
    main()
