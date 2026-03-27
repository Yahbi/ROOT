"""
Knowledge Seeder — fills ROOT's memory gaps with comprehensive knowledge.

Seeds observations, preferences, skills, reflections, errors across
multiple domains: finance, technology, decision-making, Yohan's interests,
world knowledge, and self-improvement patterns.
"""

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "memory.db"

def _now():
    return datetime.now(timezone.utc).isoformat()

def _id():
    return f"mem_{uuid.uuid4().hex[:12]}"

MEMORIES = [
    # ═══ OBSERVATIONS (about Yohan, the world, patterns) ═══
    ("observation", "Yohan builds AI systems to automate repetitive work and generate revenue", "yohan,automation,goals", "knowledge_seed"),
    ("observation", "The construction permit industry is fragmented — most cities have their own data portals with no standard API", "construction,permits,industry", "knowledge_seed"),
    ("observation", "SaaS products with recurring revenue are more valuable than one-time services", "saas,revenue,business", "knowledge_seed"),
    ("observation", "API-based products scale better than service-based businesses because they don't require proportional human effort", "api,scaling,business", "knowledge_seed"),
    ("observation", "Yohan prefers automated systems over manual processes — time freedom is a core value", "yohan,automation,preferences", "knowledge_seed"),
    ("observation", "The best investment of time is building systems that compound: each hour invested pays dividends indefinitely", "productivity,systems,compounding", "knowledge_seed"),
    ("observation", "Most people underestimate the value of data — owning unique datasets creates defensible business moats", "data,business,moats", "knowledge_seed"),
    ("observation", "Money is the primary enabler in modern society — financial independence unlocks all other freedoms", "money,freedom,philosophy", "knowledge_seed"),
    ("observation", "The AI engineering job market values practical building skills over theoretical knowledge", "ai,career,skills", "knowledge_seed"),
    ("observation", "General contractors need leads fast — whoever provides the freshest, most accurate permit data wins", "gc,leads,market", "knowledge_seed"),
    ("observation", "Python + FastAPI is Yohan's preferred stack for building backend services rapidly", "python,fastapi,tech-stack", "knowledge_seed"),
    ("observation", "Web scraping public government data is legal but requires respecting rate limits and robots.txt", "scraping,legal,ethics", "knowledge_seed"),
    ("observation", "The most successful tech entrepreneurs build multiple products that cross-sell to the same audience", "entrepreneurship,strategy,growth", "knowledge_seed"),
    ("observation", "Yohan has deep knowledge of construction permit data sources across all 50 US states", "yohan,expertise,construction", "knowledge_seed"),
    ("observation", "ROOT's architecture follows a modular pattern: core engines, agents, routes, services, plugins", "root,architecture,patterns", "knowledge_seed"),

    # ═══ PREFERENCES (Yohan's likes, dislikes, working style) ═══
    ("preference", "Yohan prefers immutable data patterns and functional programming approaches over mutation", "coding,patterns,immutability", "knowledge_seed"),
    ("preference", "Yohan values automation over manual effort — if it can be scripted, it should be", "automation,efficiency,values", "knowledge_seed"),
    ("preference", "Prefers dark mode interfaces with clean, minimal design — the ROOT dashboard aesthetic", "ui,design,dark-mode", "knowledge_seed"),
    ("preference", "Yohan values financial independence above almost everything — money is freedom", "money,values,freedom", "knowledge_seed"),
    ("preference", "Prefers building products that generate passive/recurring income over trading time for money", "income,passive,recurring", "knowledge_seed"),
    ("preference", "Likes modular, many-small-files architecture over monolithic large files", "architecture,code-style,modular", "knowledge_seed"),
    ("preference", "Prefers direct, concise communication — no fluff, no unnecessary caveats", "communication,style,direct", "knowledge_seed"),
    ("preference", "Values continuous learning — always improving skills, knowledge, and systems", "learning,growth,values", "knowledge_seed"),
    ("preference", "Prefers Python for backend, JavaScript for frontend — practical tool choices", "tech-stack,languages,preferences", "knowledge_seed"),
    ("preference", "Yohan works best when systems are self-improving — less maintenance, more creation", "workflow,self-improvement,automation", "knowledge_seed"),

    # ═══ SKILLS (procedural knowledge, how-to) ═══
    ("skill", "Web scraping pipeline: identify target → analyze HTML/API → build scraper → handle pagination → normalize data → store in SQLite/JSON", "scraping,pipeline,technique", "knowledge_seed"),
    ("skill", "FastAPI service pattern: config.py → models/ → core/ → routes/ → services/ → main.py lifespan wiring", "fastapi,architecture,pattern", "knowledge_seed"),
    ("skill", "Memory deduplication: normalize content → check first 80 chars → strengthen if duplicate → store if new", "memory,deduplication,technique", "knowledge_seed"),
    ("skill", "Opportunity evaluation framework: financial impact → time cost → risk level → alignment with goals → deal breaker check", "evaluation,framework,decision-making", "knowledge_seed"),
    ("skill", "Data pipeline pattern: discover sources → concurrent fetching with semaphore → normalize → deduplicate → cache → serve via API", "data-pipeline,pattern,technique", "knowledge_seed"),
    ("skill", "Prompt engineering: define role → set constraints → provide context → give examples → specify output format", "prompts,llm,technique", "knowledge_seed"),
    ("skill", "Revenue model analysis: identify revenue streams → estimate TAM → calculate unit economics → project growth → assess sustainability", "business,analysis,revenue", "knowledge_seed"),
    ("skill", "Risk assessment matrix: probability × impact → categorize (low/medium/high) → identify mitigations → decide accept/mitigate/avoid", "risk,assessment,framework", "knowledge_seed"),
    ("skill", "SQLite optimization: WAL mode → NORMAL sync → FTS5 for search → proper indexes → connection pooling", "sqlite,optimization,database", "knowledge_seed"),
    ("skill", "Git workflow: feature branches → conventional commits → PR with summary → squash merge → tag releases", "git,workflow,development", "knowledge_seed"),

    # ═══ REFLECTIONS (insights about self, patterns, lessons learned) ═══
    ("reflection", "The most impactful improvements to ROOT come from filling specific capability gaps rather than adding random features", "self-improvement,strategy,focus", "knowledge_seed"),
    ("reflection", "Money-making opportunities that align with existing skills (data, APIs, scraping) have the highest success probability", "money,strategy,alignment", "knowledge_seed"),
    ("reflection", "Building too many features at once leads to bugs — better to build one thing well, then iterate", "development,quality,strategy", "knowledge_seed"),
    ("reflection", "Yohan's construction data expertise is a genuine competitive advantage — few people combine tech skills with industry knowledge", "competitive-advantage,expertise,strategy", "knowledge_seed"),
    ("reflection", "The builder agent works best when given clear gap signals — vague improvement goals lead to low-impact changes", "builder,optimization,clarity", "knowledge_seed"),
    ("reflection", "Self-reflection is only valuable when it leads to concrete action — insight without action is wasted", "reflection,action,effectiveness", "knowledge_seed"),
    ("reflection", "Persistent memory is ROOT's superpower — the ability to learn from every interaction compounds over time", "memory,compounding,advantage", "knowledge_seed"),
    ("reflection", "The interest assessment engine should always ask: does this make Yohan money or save Yohan time?", "interest,assessment,criteria", "knowledge_seed"),
    ("reflection", "Good decisions require both data (quantitative assessment) and intuition (qualitative judgment) — ROOT provides the data", "decision-making,data,intuition", "knowledge_seed"),
    ("reflection", "Every capability gap is an opportunity for growth — gaps are not weaknesses, they are roadmaps", "growth,mindset,gaps", "knowledge_seed"),

    # ═══ ERRORS (lessons from failures, anti-patterns) ═══
    ("error", "BaseHTTPMiddleware in FastAPI causes ~10s blocking per request when stacked — always use pure ASGI middleware", "fastapi,performance,anti-pattern", "knowledge_seed"),
    ("error", "Variable shadowing in loops (reusing parameter name as loop var) causes silent bugs that are hard to trace", "python,bugs,shadowing", "knowledge_seed"),
    ("error", "Never run two scripts writing to the same JSON file simultaneously — causes data corruption", "concurrency,data-integrity,anti-pattern", "knowledge_seed"),
    ("error", "Hardcoding API keys in source code is a critical security vulnerability — always use environment variables", "security,api-keys,anti-pattern", "knowledge_seed"),
    ("error", "Broad exception catches (except Exception) hide real errors — catch specific exceptions when possible", "python,error-handling,anti-pattern", "knowledge_seed"),
    ("error", "Returning empty string on API error masks failures — callers can't distinguish error from empty result", "api,error-handling,design", "knowledge_seed"),
    ("error", "Sequential API fetching is too slow for large datasets — always use concurrent fetching with semaphore", "performance,concurrency,optimization", "knowledge_seed"),
    ("error", "Blacklist-based security (blocking known bad patterns) is always bypassable — whitelist approach is safer", "security,design,whitelist", "knowledge_seed"),
    ("error", "Not validating input lengths in API endpoints allows denial-of-service via oversized payloads", "security,validation,dos", "knowledge_seed"),
    ("error", "Caching without invalidation strategy leads to stale data — always include TTL or version-based cache busting", "caching,staleness,strategy", "knowledge_seed"),

    # ═══ FACTS (domain knowledge across subjects) ═══
    # -- Finance & Money --
    ("fact", "Compound interest is the most powerful force in wealth building — even small regular investments grow exponentially over decades", "finance,compounding,wealth", "knowledge_seed"),
    ("fact", "The S&P 500 has returned an average of ~10% annually over the past century, adjusted for inflation ~7%", "investing,sp500,returns", "knowledge_seed"),
    ("fact", "SaaS businesses are valued at 5-15x annual recurring revenue (ARR) — making MRR the most important metric", "saas,valuation,metrics", "knowledge_seed"),
    ("fact", "The US construction industry is worth $1.8 trillion annually — permit data touches every project", "construction,market-size,industry", "knowledge_seed"),
    ("fact", "Customer acquisition cost (CAC) should be less than 1/3 of customer lifetime value (LTV) for a healthy business", "business,metrics,unit-economics", "knowledge_seed"),
    ("fact", "Revenue diversification reduces risk — businesses with 3+ income streams survive downturns better", "business,risk,diversification", "knowledge_seed"),

    # -- Technology --
    ("fact", "Large Language Models work by predicting the next token — they are pattern matchers, not reasoners, but can simulate reasoning", "ai,llm,technology", "knowledge_seed"),
    ("fact", "FastAPI is the fastest Python web framework, achieving near-Go/Node.js performance through Starlette/uvicorn ASGI", "fastapi,performance,python", "knowledge_seed"),
    ("fact", "SQLite handles up to ~1TB databases and millions of reads per second — it's not just for small projects", "sqlite,performance,databases", "knowledge_seed"),
    ("fact", "The Socrata Open Data API (SODA) is used by 1000+ government agencies — major source for permit and public data", "socrata,open-data,government", "knowledge_seed"),
    ("fact", "Web APIs follow REST (resource-based URLs + HTTP verbs) or GraphQL (single endpoint + query language) patterns", "api,rest,graphql", "knowledge_seed"),
    ("fact", "Docker containers package code + dependencies together, ensuring identical behavior across development and production", "docker,deployment,devops", "knowledge_seed"),

    # -- Decision Making --
    ("fact", "The Eisenhower Matrix categorizes tasks by urgency and importance: Do, Schedule, Delegate, or Delete", "productivity,decision-making,framework", "knowledge_seed"),
    ("fact", "Opportunity cost: every choice has a hidden cost — the value of the best alternative you didn't choose", "economics,decision-making,opportunity-cost", "knowledge_seed"),
    ("fact", "First principles thinking: break problems down to fundamental truths, then build solutions from there", "thinking,problem-solving,first-principles", "knowledge_seed"),
    ("fact", "The Pareto Principle: 80% of results come from 20% of efforts — focus on the vital few, not the trivial many", "productivity,pareto,optimization", "knowledge_seed"),

    # -- Psychology & Self-Improvement --
    ("fact", "Dunning-Kruger effect: beginners overestimate their ability, experts underestimate — awareness helps calibrate confidence", "psychology,bias,self-awareness", "knowledge_seed"),
    ("fact", "Deliberate practice (focused effort on weaknesses with feedback) produces expertise faster than repetition alone", "learning,practice,mastery", "knowledge_seed"),
    ("fact", "Decision fatigue is real — making too many decisions degrades quality; automate routine choices", "psychology,automation,decision-fatigue", "knowledge_seed"),
    ("fact", "The brain processes information better in chunks — compartmentalized knowledge is easier to retrieve and apply", "learning,chunking,memory", "knowledge_seed"),

    # ═══ LEARNING (things ROOT has learned from interactions/experience) ═══
    ("learning", "When Yohan asks about money, he wants actionable strategies, not theoretical advice — always include next steps", "yohan,money,communication", "knowledge_seed"),
    ("learning", "The best way to evaluate an opportunity is: financial impact → time cost → risk → alignment → deal breakers", "evaluation,framework,priority", "knowledge_seed"),
    ("learning", "ROOT should always consider: does this serve Yohan's financial independence goal? If not, deprioritize it", "priorities,filter,interest", "knowledge_seed"),
    ("learning", "Construction industry contacts respond best to data-driven outreach — lead quality matters more than quantity", "construction,sales,outreach", "knowledge_seed"),
    ("learning", "When building features for ROOT, start with the highest-impact capability gap rather than the easiest one", "self-improvement,prioritization,impact", "knowledge_seed"),
    ("learning", "Yohan values speed of implementation — a working MVP beats a perfect plan that takes weeks", "development,speed,mvp", "knowledge_seed"),
    ("learning", "Money conversations should always quantify: how much revenue, what timeline, what investment required", "money,quantification,analysis", "knowledge_seed"),
    ("learning", "The most valuable skills to develop are those at the intersection of technology and industry knowledge", "skills,value,intersection", "knowledge_seed"),
    ("learning", "Compartmentalized knowledge (organized by domain) is more retrievable than flat, unsorted memories", "memory,organization,retrieval", "knowledge_seed"),
    ("learning", "ROOT's effectiveness is measured by one metric: how much it helps Yohan achieve financial independence faster", "effectiveness,metric,purpose", "knowledge_seed"),

    # ═══ GOALS (Yohan's objectives, aspirations) ═══
    ("goal", "Achieve $10,000+ monthly recurring revenue from Permit Pulse and other tech products", "revenue,permit-pulse,target", "knowledge_seed"),
    ("goal", "Make ROOT the most capable personal AI system — self-improving, money-aware, deeply personalized", "root,vision,self-improvement", "knowledge_seed"),
    ("goal", "Build multiple income streams: SaaS subscriptions, API access fees, data products, consulting", "income,diversification,streams", "knowledge_seed"),
    ("goal", "Automate lead generation and enrichment so contractors get fresh leads without manual effort", "automation,leads,product", "knowledge_seed"),
    ("goal", "Financial independence — enough passive income to not depend on any single employer or client", "financial-independence,freedom,long-term", "knowledge_seed"),
    ("goal", "Create defensible data moats — unique datasets that competitors can't easily replicate", "data,moats,competitive-advantage", "knowledge_seed"),
    ("goal", "Keep learning: AI/ML, business strategy, investment, and domain expertise in construction tech", "learning,growth,continuous", "knowledge_seed"),
    ("goal", "Scale Permit Pulse to cover all 50 states with fresh permit data and enriched contact information", "permit-pulse,scaling,coverage", "knowledge_seed"),
]

def seed():
    """Seed all memories into the database."""
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")

    inserted = 0
    skipped = 0

    for memory_type, content, tags, source in MEMORIES:
        # Check for duplicates (first 60 chars of content)
        prefix = content[:60].lower()
        existing = db.execute(
            "SELECT id FROM memories WHERE LOWER(content) LIKE ? AND superseded_by IS NULL LIMIT 1",
            (f"{prefix}%",),
        ).fetchone()

        if existing:
            skipped += 1
            continue

        mem_id = _id()
        now = _now()
        db.execute(
            "INSERT INTO memories (id, content, memory_type, tags, source, confidence, access_count, created_at, last_accessed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (mem_id, content, memory_type, tags, source, 0.9, 0, now, None),
        )
        inserted += 1

    db.commit()

    # Verify counts
    total = db.execute("SELECT COUNT(*) FROM memories WHERE superseded_by IS NULL").fetchone()[0]
    by_type = db.execute(
        "SELECT memory_type, COUNT(*) as cnt FROM memories WHERE superseded_by IS NULL GROUP BY memory_type ORDER BY cnt DESC"
    ).fetchall()

    print(f"\n{'='*50}")
    print(f"  Knowledge Seeder Results")
    print(f"{'='*50}")
    print(f"  Inserted: {inserted}")
    print(f"  Skipped (duplicates): {skipped}")
    print(f"  Total memories: {total}")
    print(f"\n  By type:")
    for row in by_type:
        print(f"    {row[0]:15} {row[1]:4}")
    print(f"{'='*50}\n")

    db.close()
    return inserted

if __name__ == "__main__":
    seed()
