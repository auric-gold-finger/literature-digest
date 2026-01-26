# Future Enhancements

## Planned Features

### 1. Compound Topic Support in topics.csv
**Status:** Planned  
**Priority:** Medium  
**Related to:** Intersection query implementation

**Description:**  
Add a new column `intersection_with` to topics.csv that specifies required co-occurring topics. This would allow defining compound topics like "GLP-1 + Muscle" as a single selectable option in the UI.

**Proposed schema change:**
```csv
name,query_fragment,active,priority,intersection_with
GLP-1 & Muscle,<auto>,TRUE,normal,Metabolism;Protein & Muscle
```

**Implementation notes:**
- When a topic has `intersection_with` populated, use `build_intersection_query()` instead of `build_pubmed_query()`
- The `query_fragment` could be auto-generated from the referenced topics
- Update `app.py` UI to display compound topics differently (e.g., with "∩" symbol)
- Consider allowing users to create ad-hoc intersections in the UI

**Dependencies:**
- [x] Intersection query function (`build_intersection_query`)
- [x] Pre-defined intersection templates (`INTERSECTION_TEMPLATES`)
- [ ] UI changes in app.py to expose intersection queries
- [ ] Config loader updates for new column

---

### 2. AI Scoring Prompt Tuning for Attia Framework
**Status:** Planned  
**Priority:** High

**Description:**  
Update the relevance scoring criteria in `utils/gemini_headless.py` to explicitly weight papers based on:
- Four Horsemen relevance (CVD, cancer, neurodegeneration, metabolic disease)
- Exercise/physical capacity (Zone 2, VO2max, strength, stability)
- Survey hot topics (menopause/HRT, GLP-1, ApoB/Lp(a), protein, statins, pain)

---

### 3. Journal Quality Tiers
**Status:** Planned  
**Priority:** Medium

**Description:**  
Create `sheet_import/journals_whitelist.csv` with top-tier journals (NEJM, Lancet, JAMA, Cell, Nature Medicine, etc.) and apply a +1-2 score boost similar to author whitelist.

---

### 4. Activate Priority Field
**Status:** ✅ Implemented  
**Priority:** Low

**Description:**  
The `priority` column exists in topics.csv but is currently unused. Implement logic to:
- Always include `priority=always` topics regardless of preset
- Give `priority=high` topics a +1 boost to relevance score

**Implementation (Jan 2026):**
- Added `priority: "high"` to Sleep and Hormones & HRT topics in defaults.json
- Updated AI scoring prompt to explicitly weight sleep/hormones higher
- Added `apply_priority_topic_boost()` function in gemini_headless.py
- Added `load_high_priority_topics()` function in config_loader.py
- Both daily_digest.py and frontier_digest.py now apply +1 boost to papers matching high-priority topic keywords

---

### 5. User Feedback Loop
**Status:** Future consideration  
**Priority:** Low

**Description:**  
Track which papers get engagement (Slack reactions, Notion page views) and use this to refine topic weights and scoring over time.

---

## Completed

### ✅ Add missing survey-driven topics (Jan 2026)
Added to `sheet_import/topics.csv`:
- Protein & Muscle (sarcopenia, leucine, muscle mass, anabolic resistance)
- Statins & Lipid Drugs (statin*, atorvastatin, bempedoic acid, PCSK9 inhibitors)
- Pain & Musculoskeletal (chronic pain, arthritis, Nav1.8, suzetrigine)
- Menopause & Perimenopause (with priority=high)
- Updated Hormones & HRT to include menopause/perimenopause terms

### ✅ Intersection query support (Jan 2026)
Added to `utils/query_builder.py`:
- `build_intersection_query()` function for AND-logic between concept groups
- `INTERSECTION_TEMPLATES` dict with 8 pre-defined multi-domain searches:
  - GLP-1 & Muscle Preservation
  - Menopause & Bone Health
  - Exercise & Cognitive Health
  - Statins & Muscle Effects
  - ApoB & Interventions
  - Protein Intake & Aging
  - Sleep & Cognitive Health
  - VO2max & Mortality
