# Entity Correction Workflow

**Phase 2, Day 4** — how to review and fix the entities Agent 2 extracted.
Written so a non-technical reviewer can follow it end to end.

---

## The Idea in One Paragraph

Agent 2 made educated guesses about what each page is about (its market,
country, region, industry). Every guess has a **status** and a **confidence
score**. Nothing is ever deleted or overwritten: if a guess is wrong you mark
it *rejected* (it stays visible but stops being used), or *corrected* (the
fixed value is stored next to the original guess). Every change is logged.

## The Four Statuses

| Status | Meaning | Who sets it |
|---|---|---|
| `extracted` | Fresh guess, not reviewed yet (default) | Agent 2 |
| `approved` | A human checked it — it's correct | Reviewer |
| `corrected` | A human fixed it — corrected value stored, original kept | Reviewer |
| `rejected` | Wrong — kept for the record, excluded from future use | Reviewer |

## Step-by-Step Review Process

**1. Get the review list** (guesses the system was less sure about):

```
python scripts/10_entity_corrections.py list-low-confidence
```

This writes a CSV into `reports/` (e.g. `low_confidence_entities_<date>.csv`).
Open it in Excel. Each row = one guess about one page: the page URL, what was
guessed (`entity_name`), what kind of thing it is (`entity_type`), where the
guess came from (`source_field`), and how confident the system was
(`confidence_score`, 0 to 1). Everything under 0.70 is on this list.

**2. Judge each row.** Open the URL, look at the page, ask: is this guess right?

**3. Act on it** — copy the row's `node_entity_id` from the CSV and run ONE of:

```
# It's correct:
python scripts/10_entity_corrections.py approve --id <node_entity_id>

# It's wrong, no replacement needed:
python scripts/10_entity_corrections.py reject --id <node_entity_id> --notes "why"

# It's wrong, and you know the right value:
python scripts/10_entity_corrections.py correct --id <node_entity_id> --value "Right Value"
```

**4. Check overall health any time:**

```
python scripts/10_entity_corrections.py audit
```

Shows the status counts, the confidence bands, and whether any duplicate
entities exist.

## Duplicate Merging

If the same market ever gets stored twice under different spellings
("Power Tools Market" vs "Power Tool Market"), fix it with:

```
python scripts/10_entity_corrections.py merge-duplicates          # preview only
python scripts/10_entity_corrections.py merge-duplicates --apply  # actually merge
```

The variant used by more pages is kept; the other's page links are moved over,
then it's removed. Preview mode is the default — nothing changes without
`--apply`. (Day 4 run: 4 singular/plural pairs found and merged; the dedup
key in `config/taxonomy.py` now folds plurals so new ones can't be created.)

## Safety Guarantees

- **Originals always survive.** `extracted_value` (what Agent 2 actually found
  on the page) is never modified by any command.
- **Everything is logged.** Every approve/reject/correct/merge writes a row to
  `entity_extraction_logs` with what changed and when.
- **Merges preview by default.** `--apply` is required to change data.
- **Rejected guesses are excluded, not erased** — Agent 3 (relationship
  mapping) and later phases must skip `status='rejected'` rows; the data
  stays for audit.

## Current State (Day 4 close)

- 1,873 page-to-entity mappings, all statuses visible via `audit`
- Confidence: 1,488 high (≥0.9) · 341 good (0.7–0.9) · 44 review (0.5–0.7) · 0 low (<0.5)
- The 44 review-band mappings are exported in `reports/low_confidence_entities_*.csv`
- 0 duplicate entities after the Day 4 merge
