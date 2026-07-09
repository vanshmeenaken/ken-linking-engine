from datetime import datetime, timezone
import uuid

from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship

from database.db import Base


class ContentNode(Base):
    """One row per Ken Research page: metadata, classification, link counts,
    and scores. The core table populated by Agent 1 (Phase 1)."""

    __tablename__ = "content_nodes"

    node_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    url = Column(String, unique=True, nullable=False)
    canonical_url = Column(String)
    title = Column(String)
    meta_title = Column(String)
    meta_description = Column(String)
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
    published_date = Column(String)
    updated_date = Column(String)
    indexability_status = Column(String)
    crawl_depth = Column(Integer)
    internal_links_in = Column(Integer, default=0)
    internal_links_out = Column(Integer, default=0)
    orphan_status = Column(String)
    page_authority_score = Column(Float)
    search_opportunity_score = Column(Float)
    ai_readiness_score = Column(Float)
    status = Column(String, default="active")
    created_at = Column(String, default=lambda: datetime.now(timezone.utc).isoformat())
    updated_at = Column(String, default=lambda: datetime.now(timezone.utc).isoformat())

    outgoing_edges = relationship("RelationshipEdge", foreign_keys="RelationshipEdge.source_node_id", back_populates="source_node", cascade="all, delete-orphan")
    incoming_edges = relationship("RelationshipEdge", foreign_keys="RelationshipEdge.target_node_id", back_populates="target_node", cascade="all, delete-orphan")
    crawl_logs = relationship("CrawlLog", back_populates="content_node", cascade="all, delete-orphan")


class ContentEntity(Base):
    """An extracted entity (market, industry, country, company, etc.).
    Schema only in Phase 1 — populated by Agent 2 (Entity Extraction), Phase 2."""

    __tablename__ = "content_entities"

    entity_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_name = Column(String, nullable=False)
    entity_type = Column(String)
    normalized_name = Column(String)
    aliases = Column(String)
    parent_entity_id = Column(String, ForeignKey("content_entities.entity_id"))
    industry = Column(String)
    country = Column(String)
    region = Column(String)
    confidence_score = Column(Float, default=0.0)
    created_at = Column(String, default=lambda: datetime.now(timezone.utc).isoformat())
    updated_at = Column(String, default=lambda: datetime.now(timezone.utc).isoformat())

    __table_args__ = (UniqueConstraint("normalized_name", "entity_type"),)

    parent_entity = relationship("ContentEntity", remote_side=[entity_id], backref="child_entities")


class RelationshipEdge(Base):
    """A typed, scored relationship between two content nodes (or entities).
    Schema only in Phase 1 — populated by Agent 3 (Relationship Mapping), Phase 2."""

    __tablename__ = "relationship_edges"

    edge_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_node_id = Column(String, ForeignKey("content_nodes.node_id"), nullable=False)
    target_node_id = Column(String, ForeignKey("content_nodes.node_id"), nullable=False)
    source_entity_id = Column(String, ForeignKey("content_entities.entity_id"))
    target_entity_id = Column(String, ForeignKey("content_entities.entity_id"))
    relationship_type = Column(String)
    relationship_direction = Column(String)
    confidence_score = Column(Float, default=0.0)
    semantic_similarity_score = Column(Float)
    entity_overlap_score = Column(Float)
    geo_match_score = Column(Float)
    market_match_score = Column(Float)
    business_value_score = Column(Float)
    seo_value_score = Column(Float)
    created_by = Column(String)
    reviewed_by = Column(String)
    status = Column(String, default="pending")
    created_at = Column(String, default=lambda: datetime.now(timezone.utc).isoformat())
    updated_at = Column(String, default=lambda: datetime.now(timezone.utc).isoformat())

    __table_args__ = (UniqueConstraint("source_node_id", "target_node_id", "relationship_type"),)

    source_node = relationship("ContentNode", foreign_keys=[source_node_id], back_populates="outgoing_edges")
    target_node = relationship("ContentNode", foreign_keys=[target_node_id], back_populates="incoming_edges")
    source_entity = relationship("ContentEntity", foreign_keys=[source_entity_id])
    target_entity = relationship("ContentEntity", foreign_keys=[target_entity_id])


class NodeEntity(Base):
    """Page-to-entity mapping with per-extraction provenance and confidence.
    Phase 2 core join table, populated by Agent 2."""

    __tablename__ = "node_entities"

    node_entity_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    node_id = Column(String, ForeignKey("content_nodes.node_id"), nullable=False)
    entity_id = Column(String, ForeignKey("content_entities.entity_id"), nullable=False)
    entity_role = Column(String, nullable=False)
    source_field = Column(String)
    extracted_value = Column(String)
    normalized_value = Column(String)
    confidence_score = Column(Float, default=0.0)
    extraction_method = Column(String)
    status = Column(String, default="extracted")
    created_at = Column(String, default=lambda: datetime.now(timezone.utc).isoformat())
    updated_at = Column(String, default=lambda: datetime.now(timezone.utc).isoformat())

    __table_args__ = (UniqueConstraint("node_id", "entity_id", "entity_role"),)

    content_node = relationship("ContentNode", foreign_keys=[node_id])
    entity = relationship("ContentEntity", foreign_keys=[entity_id])


class EntityExtractionLog(Base):
    """Audit trail of Agent 2 extraction runs (Phase 2)."""

    __tablename__ = "entity_extraction_logs"

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, nullable=False)
    node_id = Column(String, ForeignKey("content_nodes.node_id"))
    operation = Column(String)
    status = Column(String)
    entities_found = Column(Integer, default=0)
    low_confidence_count = Column(Integer, default=0)
    error = Column(Text)
    notes = Column(Text)
    created_at = Column(String, default=lambda: datetime.now(timezone.utc).isoformat())


class SemanticEmbedding(Base):
    """Per-page semantic representation (TF-IDF sparse vector as JSON in the
    Phase 2 MVP; model name recorded so an embedding upgrade is additive)."""

    __tablename__ = "semantic_embeddings"

    embedding_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    node_id = Column(String, ForeignKey("content_nodes.node_id"), nullable=False, unique=True)
    text_hash = Column(String, nullable=False)
    source_text = Column(Text)
    embedding_model = Column(String)
    embedding_vector = Column(Text)
    created_at = Column(String, default=lambda: datetime.now(timezone.utc).isoformat())
    updated_at = Column(String, default=lambda: datetime.now(timezone.utc).isoformat())


class SeoOpportunity(Base):
    """Early Agent 4 output: one open opportunity per page per type (Phase 2)."""

    __tablename__ = "seo_opportunities"

    opportunity_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    node_id = Column(String, ForeignKey("content_nodes.node_id"), nullable=False)
    opportunity_type = Column(String, nullable=False)
    priority = Column(String)
    reason = Column(Text)
    evidence = Column(Text)
    seo_score = Column(Float, default=0.0)
    business_score = Column(Float, default=0.0)
    status = Column(String, default="open")
    created_at = Column(String, default=lambda: datetime.now(timezone.utc).isoformat())
    updated_at = Column(String, default=lambda: datetime.now(timezone.utc).isoformat())

    __table_args__ = (UniqueConstraint("node_id", "opportunity_type"),)


class IntegrationPlaceholder(Base):
    """GSC/GA4 schema-readiness rows while credentials are arranged (Phase 2)."""

    __tablename__ = "integration_placeholders"

    integration_id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String, nullable=False)
    node_id = Column(String, ForeignKey("content_nodes.node_id"))
    url = Column(String)
    metric_name = Column(String)
    metric_value = Column(Float)
    date_range = Column(String)
    status = Column(String, default="placeholder")
    notes = Column(Text)
    created_at = Column(String, default=lambda: datetime.now(timezone.utc).isoformat())


class CrawlLog(Base):
    """Audit trail of every load/enrichment operation run against a URL."""

    __tablename__ = "crawl_logs"

    crawl_id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String, nullable=False)
    node_id = Column(String, ForeignKey("content_nodes.node_id"))
    operation = Column(String)
    status = Column(String)
    http_status = Column(Integer)
    crawl_depth = Column(Integer)
    error = Column(Text)
    notes = Column(Text)
    crawled_at = Column(String, default=lambda: datetime.now(timezone.utc).isoformat())

    content_node = relationship("ContentNode", back_populates="crawl_logs")


# Indexes for performance
Index("ix_content_nodes_url", ContentNode.url)
Index("ix_content_nodes_content_type", ContentNode.content_type)
Index("ix_content_nodes_industry", ContentNode.industry)
Index("ix_content_nodes_country", ContentNode.country)
Index("ix_content_nodes_status", ContentNode.status)
Index("ix_content_nodes_orphan_status", ContentNode.orphan_status)

Index("ix_content_entities_entity_type", ContentEntity.entity_type)
Index("ix_content_entities_normalized_name", ContentEntity.normalized_name)
Index("ix_content_entities_parent_entity_id", ContentEntity.parent_entity_id)

Index("ix_relationship_edges_source_node_id", RelationshipEdge.source_node_id)
Index("ix_relationship_edges_target_node_id", RelationshipEdge.target_node_id)
Index("ix_relationship_edges_relationship_type", RelationshipEdge.relationship_type)
Index("ix_relationship_edges_status", RelationshipEdge.status)

Index("ix_crawl_logs_url", CrawlLog.url)
Index("ix_crawl_logs_status", CrawlLog.status)

Index("ix_node_entities_node_id", NodeEntity.node_id)
Index("ix_node_entities_entity_id", NodeEntity.entity_id)
Index("ix_node_entities_status", NodeEntity.status)
Index("ix_node_entities_confidence", NodeEntity.confidence_score)

Index("ix_extraction_logs_run_id", EntityExtractionLog.run_id)
Index("ix_extraction_logs_node_id", EntityExtractionLog.node_id)
Index("ix_extraction_logs_status", EntityExtractionLog.status)

Index("ix_semantic_embeddings_text_hash", SemanticEmbedding.text_hash)

Index("ix_seo_opportunities_node_id", SeoOpportunity.node_id)
Index("ix_seo_opportunities_type", SeoOpportunity.opportunity_type)
Index("ix_seo_opportunities_priority", SeoOpportunity.priority)
Index("ix_seo_opportunities_status", SeoOpportunity.status)

Index("ix_integration_placeholders_source", IntegrationPlaceholder.source)
Index("ix_integration_placeholders_node_id", IntegrationPlaceholder.node_id)
Index("ix_integration_placeholders_metric", IntegrationPlaceholder.metric_name)
