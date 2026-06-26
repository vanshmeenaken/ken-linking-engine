# DATABASE RELATIONSHIPS

## Foreign Key Diagram

```
content_entities (self-reference)
  └─ parent_entity_id → content_entities.entity_id
  
relationship_edges
  ├─ source_node_id → content_nodes.node_id
  ├─ target_node_id → content_nodes.node_id
  ├─ source_entity_id → content_entities.entity_id
  └─ target_entity_id → content_entities.entity_id
  
crawl_logs
  └─ node_id → content_nodes.node_id
```

## What This Means

**content_entities has hierarchy:**
- Entity can have parent (same table)
- Creates tree: Segment → Market → Industry → Region

**relationship_edges connects everything:**
- Page to Page (source_node → target_node)
- Entity to Entity (source_entity → target_entity)
- Supports cross-type relationships

**crawl_logs tracks operations:**
- Every insert/update logged
- Links back to content_nodes
- Full audit trail

---

**See full details:** `01-SCHEMA.md` and `02-SCHEMA-VISUAL.md`
