# Manual Interlinking Workbench (/users)

## Purpose

The main dashboard reviews links the system proposes. This page is the
opposite direction: a person decides the interlinking themselves. Paste a
report URL, read that page's real content here, see every related page the
system can find, choose the exact paragraph, and record the decision.

Reached from the green **Users** button on the main dashboard, or directly at
`http://localhost:8000/users`.

## The five steps on the page

1. **Enter the report URL.** Any Ken Research URL. Both live forms work (with
   or without the `/industry-reports/` prefix) - they resolve to the same
   inventory row.
2. **Read the report's own content.** Sections and paragraphs are fetched
   live. Click the paragraph where the link belongs. Sections that must never
   carry a cross-report link are shown in red and are not clickable: the
   page's own opening stat, Market Overview, FAQ, author bio, CTA, table of
   contents, methodology.
3. **Pick the page to link to.** Candidates are labelled `regional`,
   `adjacent`, or `adjacent regional`, and tagged by where they came from -
   `inventory` (our 500-page sample, including trusted relationship edges) or
   `sitemap` (Ken's live 5,000-page sitemap).
4. **Record the decision.** The page offers several ways to word the
   sentence, each placing the anchor in a different position (opening the
   sentence, mid-clause as an appositive, or as the sentence's subject, plus
   a trailing mention labelled as the weakest). Click one to load it, edit it
   freely, or ignore them all and type your own. Whatever ends up in the
   final-sentence box is what gets stored and handed to the web team. Add the
   anchor text, an optional note, and your name.
5. **Review saved decisions.** Everything saved for that report, with the
   exact sentence to paste, deletable.

## Several links on one report

Saving keeps the report loaded, so the normal flow is: pick a paragraph, pick
a target, save, then repeat. The confirmation reports the running total for
that report, paragraphs that already carry a link are marked green in the
content pane, and re-using one paragraph is called out ("this paragraph
already carries a link to ..."). That mirrors the automated pipeline's rule
that two links must not share a sentence, but here it is a warning rather
than a block: it is the user's own workbench and they may have a reason.

Sentence suggestions never invent a fact. They rearrange the paragraph's own
wording and add a connector naming the target, so a suggestion cannot
introduce a market number that was not already there.

## Where candidates come from

Inventory first, sitemap second - and always in that order, because an
inventory match can carry a trusted relationship edge (already scored and
gated by Agent 3) while a sitemap match is inferred from the slug alone.

| Source | Meaning |
| --- | --- |
| `inventory_edge` | A trusted relationship edge already in the graph |
| `inventory_subject` | Another inventory page that passes the subject gate |
| `sitemap` | From Ken's public sitemap, outside our 500-page sample |

Every candidate, from either source, must pass the SAME market/technology
subject gate the automated pipeline uses (`market_technology_relevance`):
market relevance >= 0.30, technology relevance >= 0.50. Sharing only a
country never qualifies a page. When nothing passes, the page says so
honestly rather than padding the list.

## The sitemap cache

`analysis/sitemap_index.py` reads `https://www.kenresearch.com/sitemap.xml`
and the child sitemaps worth indexing (product, article, casestudy, survey,
pov, blog), caching ~5,000 URLs into `sitemap_urls`. Refresh from the button
in the page header, or:

```powershell
python -c "from analysis.sitemap_index import refresh_sitemap_cache; print(refresh_sitemap_cache())"
```

## Stored separately from machine suggestions

Decisions go to `manual_link_plans`, never to `link_recommendations`. That
separation is deliberate and tested: it must always be possible to tell which
links the machine proposed and which a person wrote by hand.

## Endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /api/manual/related?url=` | Related pages: inventory first, sitemap top-up |
| `GET /api/manual/content?url=` | The page's real sections and paragraphs |
| `POST /api/manual/links` | Save one human decision |
| `GET /api/manual/links?url=` | Saved decisions (all, or one report) |
| `DELETE /api/manual/links/{id}` | Remove a decision |
| `GET /api/manual/sitemap/status` | Cache size and last fetch time |
| `POST /api/manual/sitemap/refresh` | Re-fetch the sitemap |

Reading a page is a live, read-only fetch; nothing about the live site is
ever modified.

## Verification

```powershell
python scripts/37_manual_linking_migration.py
python -m pytest tests/test_manual_workbench.py -q
```

Then open `http://localhost:8000/users` and paste a report URL.
