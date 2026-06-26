from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from database.db import Base


class ContentNode(Base):
    __tablename__ = "content_nodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    node_id = Column(String, unique=True)          # UUID text key used by loader
    url = Column(String, unique=True, nullable=False)
    canonical_url = Column(String)
    title = Column(String)
    meta_title = Column(String)
    meta_description = Column(Text)
    h1 = Column(String)
    content_type = Column(String)
    industry = Column(String)
    sub_industry = Column(String)
    market = Column(String)
    segment = Column(String)
    country = Column(String)
    region = Column(String)
    global_or_local = Column(String)
    intent_stage = Column(String)
    business_priority = Column(String)
    word_count = Column(Integer, default=0)
    published_date = Column(DateTime)
    updated_date = Column(DateTime)
    indexability_status = Column(String)
    crawl_depth = Column(Integer)
    internal_links_in = Column(Integer, default=0)
    internal_links_out = Column(Integer, default=0)
    orphan_status = Column(String)
    page_authority_score = Column(Float)
    search_opportunity_score = Column(Float)
    ai_readiness_score = Column(Float)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

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
    node_id = Column(String)
    operation = Column(String)
    status = Column(String)
    error_message = Column(Text)
    notes = Column(Text)
    crawled_at = Column(DateTime, default=datetime.utcnow)
