"""
Seed evolution log entries and knowledge memories for ROOT.

Creates 50+ evolution entries in data/evolution_log.json
and 100+ diverse knowledge memories in the memory database.
"""

import json
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Project root setup
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.memory_engine import MemoryEngine
from backend.models.memory import MemoryEntry, MemoryType

# ── Paths ──────────────────────────────────────────────────────
EVOLUTION_LOG = PROJECT_ROOT / "data" / "evolution_log.json"

# ── Helpers ────────────────────────────────────────────────────

def _rand_ts(days_back: int = 7) -> str:
    """Random ISO timestamp within the last N days."""
    now = datetime.now(timezone.utc)
    offset = random.uniform(0, days_back * 86400)
    ts = now - timedelta(seconds=offset)
    return ts.isoformat()


def _evo_id() -> str:
    return f"evo_{uuid.uuid4().hex[:12]}"


# ── Evolution Entries ──────────────────────────────────────────

EVOLUTION_ENTRIES = [
    # Skills created (15)
    {"action_type": "skill_created", "description": "Created skill: opportunity-evaluation — score business ideas by feasibility, market size, and alignment",
     "details": {"skill": "opportunity-evaluation", "version": "1.0"}, "impact_score": 0.85},
    {"action_type": "skill_created", "description": "Created skill: risk-assessment — evaluate downside exposure and mitigation strategies",
     "details": {"skill": "risk-assessment", "version": "1.0"}, "impact_score": 0.80},
    {"action_type": "skill_created", "description": "Created skill: interest-alignment — match opportunities to Yohan's stated interests and goals",
     "details": {"skill": "interest-alignment", "version": "1.0"}, "impact_score": 0.90},
    {"action_type": "skill_created", "description": "Created skill: revenue-modeling — project revenue curves for SaaS and service businesses",
     "details": {"skill": "revenue-modeling", "version": "1.0"}, "impact_score": 0.82},
    {"action_type": "skill_created", "description": "Created skill: investment-analysis — DCF, comparable analysis, and ROI estimation",
     "details": {"skill": "investment-analysis", "version": "1.0"}, "impact_score": 0.78},
    {"action_type": "skill_created", "description": "Created skill: competitive-moat — identify defensibility and barriers to entry",
     "details": {"skill": "competitive-moat", "version": "1.0"}, "impact_score": 0.83},
    {"action_type": "skill_created", "description": "Created skill: market-positioning — analyze positioning relative to competitors and market gaps",
     "details": {"skill": "market-positioning", "version": "1.0"}, "impact_score": 0.76},
    {"action_type": "skill_created", "description": "Created skill: domain-learning — rapidly absorb domain knowledge from documents and APIs",
     "details": {"skill": "domain-learning", "version": "1.0"}, "impact_score": 0.88},
    {"action_type": "skill_created", "description": "Created skill: budget-tracking — monitor spending, burn rate, and financial health",
     "details": {"skill": "budget-tracking", "version": "1.0"}, "impact_score": 0.72},
    {"action_type": "skill_created", "description": "Created skill: lead-scoring — rank leads by conversion probability using permit and property signals",
     "details": {"skill": "lead-scoring", "version": "1.0"}, "impact_score": 0.91},
    {"action_type": "skill_created", "description": "Created skill: outreach-templating — generate personalized cold emails and SMS sequences",
     "details": {"skill": "outreach-templating", "version": "1.0"}, "impact_score": 0.74},
    {"action_type": "skill_created", "description": "Created skill: data-pipeline-design — architect ETL flows from raw sources to clean datasets",
     "details": {"skill": "data-pipeline-design", "version": "1.0"}, "impact_score": 0.86},
    {"action_type": "skill_created", "description": "Created skill: api-integration — connect to REST/GraphQL APIs with auth, rate limits, and retries",
     "details": {"skill": "api-integration", "version": "1.0"}, "impact_score": 0.84},
    {"action_type": "skill_created", "description": "Created skill: cost-optimization — reduce infrastructure and API costs without degrading performance",
     "details": {"skill": "cost-optimization", "version": "1.0"}, "impact_score": 0.77},
    {"action_type": "skill_created", "description": "Created skill: user-research — synthesize user feedback into actionable product insights",
     "details": {"skill": "user-research", "version": "1.0"}, "impact_score": 0.73},

    # Knowledge absorbed (10)
    {"action_type": "knowledge_absorbed", "description": "Absorbed knowledge: Transformer architecture fundamentals — attention mechanisms, positional encoding, layer normalization",
     "details": {"domain": "AI/ML", "sources": 3, "concepts": 12}, "impact_score": 0.87},
    {"action_type": "knowledge_absorbed", "description": "Absorbed knowledge: SaaS financial metrics — ARR, MRR, churn rate, LTV/CAC ratio, Rule of 40",
     "details": {"domain": "finance", "sources": 5, "concepts": 18}, "impact_score": 0.92},
    {"action_type": "knowledge_absorbed", "description": "Absorbed knowledge: US construction permit landscape — Accela, EnerGov, Socrata open data portals",
     "details": {"domain": "construction", "sources": 8, "concepts": 25}, "impact_score": 0.95},
    {"action_type": "knowledge_absorbed", "description": "Absorbed knowledge: Web scraping best practices — rate limiting, proxy rotation, robots.txt compliance",
     "details": {"domain": "engineering", "sources": 4, "concepts": 15}, "impact_score": 0.79},
    {"action_type": "knowledge_absorbed", "description": "Absorbed knowledge: Agent orchestration patterns — ReAct, tool-use loops, multi-agent delegation",
     "details": {"domain": "AI/agents", "sources": 6, "concepts": 20}, "impact_score": 0.88},
    {"action_type": "knowledge_absorbed", "description": "Absorbed knowledge: Real estate data enrichment — parcel records, ArcGIS feature services, Regrid MVT tiles",
     "details": {"domain": "real_estate", "sources": 4, "concepts": 14}, "impact_score": 0.83},
    {"action_type": "knowledge_absorbed", "description": "Absorbed knowledge: Email deliverability — SPF, DKIM, DMARC, warm-up sequences, bounce handling",
     "details": {"domain": "marketing", "sources": 3, "concepts": 10}, "impact_score": 0.71},
    {"action_type": "knowledge_absorbed", "description": "Absorbed knowledge: Behavioral psychology in product design — nudge theory, habit loops, variable rewards",
     "details": {"domain": "psychology", "sources": 5, "concepts": 16}, "impact_score": 0.76},
    {"action_type": "knowledge_absorbed", "description": "Absorbed knowledge: SQLite performance tuning — WAL mode, PRAGMA settings, FTS5 indexing strategies",
     "details": {"domain": "databases", "sources": 3, "concepts": 9}, "impact_score": 0.81},
    {"action_type": "knowledge_absorbed", "description": "Absorbed knowledge: Startup fundraising mechanics — SAFE notes, convertible notes, priced rounds, dilution",
     "details": {"domain": "finance", "sources": 4, "concepts": 13}, "impact_score": 0.74},

    # Capabilities added (8)
    {"action_type": "capability_added", "description": "Added capability: Interest Engine — tracks and scores Yohan's interests to surface relevant opportunities",
     "details": {"module": "interest_engine", "endpoints": 4}, "impact_score": 0.93},
    {"action_type": "capability_added", "description": "Added capability: Money Engine — evaluates revenue potential and financial viability of opportunities",
     "details": {"module": "money_engine", "endpoints": 3}, "impact_score": 0.91},
    {"action_type": "capability_added", "description": "Added capability: Plugin Engine — dynamically load and execute agent plugins from filesystem",
     "details": {"module": "plugin_engine", "endpoints": 5}, "impact_score": 0.88},
    {"action_type": "capability_added", "description": "Added capability: Builder Agent — generates code artifacts and project scaffolds on demand",
     "details": {"module": "builder_agent", "endpoints": 2}, "impact_score": 0.85},
    {"action_type": "capability_added", "description": "Added capability: Memory Engine — persistent FTS5-backed knowledge store with confidence decay",
     "details": {"module": "memory_engine", "endpoints": 6}, "impact_score": 0.96},
    {"action_type": "capability_added", "description": "Added capability: Evolution Tracker — logs every self-improvement action for introspection",
     "details": {"module": "evolution_tracker", "endpoints": 3}, "impact_score": 0.82},
    {"action_type": "capability_added", "description": "Added capability: Strategy Council — multi-agent deliberation for high-stakes decisions",
     "details": {"module": "strategy_council", "endpoints": 2}, "impact_score": 0.89},
    {"action_type": "capability_added", "description": "Added capability: Dashboard API — real-time stats, memory search, and evolution timeline for frontend",
     "details": {"module": "dashboard_api", "endpoints": 8}, "impact_score": 0.80},

    # Reflection insights (8)
    {"action_type": "reflection_insight", "description": "Reflection: Breadth-first knowledge absorption is more valuable early on than deep-diving a single domain",
     "details": {"trigger": "After absorbing 5 domains in parallel", "lesson": "Cross-domain pattern matching accelerates insight generation"}, "impact_score": 0.78},
    {"action_type": "reflection_insight", "description": "Reflection: Yohan responds best to concrete, actionable recommendations rather than abstract analysis",
     "details": {"trigger": "Observed engagement patterns", "lesson": "Lead with 'do this next' rather than 'consider these factors'"}, "impact_score": 0.84},
    {"action_type": "reflection_insight", "description": "Reflection: Memory deduplication prevents knowledge bloat but must preserve nuance in similar-but-distinct entries",
     "details": {"trigger": "Duplicate detection merging distinct insights", "lesson": "Use longer prefix matching (80+ chars) for dedup"}, "impact_score": 0.72},
    {"action_type": "reflection_insight", "description": "Reflection: Evolution log entries with higher impact scores correlate with capabilities that get used most",
     "details": {"trigger": "Analyzing access patterns", "lesson": "Impact scoring is a useful proxy for actual utility"}, "impact_score": 0.69},
    {"action_type": "reflection_insight", "description": "Reflection: Permit Pulse domain knowledge transfers directly to ROOT opportunity analysis",
     "details": {"trigger": "Cross-project knowledge reuse", "lesson": "Construction + tech intersection is a high-value niche"}, "impact_score": 0.87},
    {"action_type": "reflection_insight", "description": "Reflection: Batch processing with concurrency limits outperforms sequential fetching by 10-50x",
     "details": {"trigger": "ArcGIS endpoint scraping optimization", "lesson": "Semaphore-bounded asyncio.gather is the sweet spot"}, "impact_score": 0.81},
    {"action_type": "reflection_insight", "description": "Reflection: Small, frequent commits to the evolution log create a clearer growth narrative than large dumps",
     "details": {"trigger": "Reviewing evolution timeline", "lesson": "Granular logging enables better trend analysis"}, "impact_score": 0.65},
    {"action_type": "reflection_insight", "description": "Reflection: The most valuable memories are those accessed repeatedly — high access_count is a signal of utility",
     "details": {"trigger": "Memory stats analysis", "lesson": "Strengthen high-access memories proactively"}, "impact_score": 0.73},

    # Gaps identified (5)
    {"action_type": "gap_identified", "description": "Gap identified: No automated way to validate if a Socrata endpoint is still alive before fetching",
     "details": {"area": "data_pipeline", "severity": "medium", "proposed_fix": "Add health-check ping with timeout before batch fetch"}, "impact_score": 0.68},
    {"action_type": "gap_identified", "description": "Gap identified: Memory engine lacks semantic similarity search — only keyword FTS5 matching",
     "details": {"area": "memory_engine", "severity": "high", "proposed_fix": "Add embedding-based similarity using local model or API"}, "impact_score": 0.82},
    {"action_type": "gap_identified", "description": "Gap identified: No notification system when new high-value opportunities are detected",
     "details": {"area": "interest_engine", "severity": "medium", "proposed_fix": "Add webhook/email alerts for opportunities scoring above 0.8"}, "impact_score": 0.75},
    {"action_type": "gap_identified", "description": "Gap identified: Evolution log has no rollback mechanism if a bad capability is deployed",
     "details": {"area": "evolution_tracker", "severity": "low", "proposed_fix": "Add revert_evolution() that marks entry as rolled back"}, "impact_score": 0.58},
    {"action_type": "gap_identified", "description": "Gap identified: Strategy Council does not weight agent opinions by domain expertise relevance",
     "details": {"area": "strategy_council", "severity": "medium", "proposed_fix": "Add expertise-weighted voting based on agent-domain affinity scores"}, "impact_score": 0.71},

    # Code proposed (9)
    {"action_type": "code_proposed", "description": "Proposed improvement in data_pipeline: Add retry logic with exponential backoff for failed API fetches",
     "details": {"area": "data_pipeline", "rationale": "20% of ArcGIS endpoints fail on first try but succeed on retry"}, "impact_score": 0.77},
    {"action_type": "code_proposed", "description": "Proposed improvement in memory: Add memory clustering by topic for faster contextual retrieval",
     "details": {"area": "memory", "rationale": "Tag-based grouping is too coarse; need semantic clusters"}, "impact_score": 0.74},
    {"action_type": "code_proposed", "description": "Proposed improvement in dashboard: Add real-time WebSocket updates for evolution log changes",
     "details": {"area": "dashboard", "rationale": "Polling every 30s misses rapid evolution bursts"}, "impact_score": 0.63},
    {"action_type": "code_proposed", "description": "Proposed improvement in security: Implement API key rotation for external service credentials",
     "details": {"area": "security", "rationale": "Static keys increase exposure window if compromised"}, "impact_score": 0.79},
    {"action_type": "code_proposed", "description": "Proposed improvement in performance: Pre-compute and cache strategy council results for common queries",
     "details": {"area": "performance", "rationale": "Council deliberation takes 3-8s; cache frequent patterns"}, "impact_score": 0.70},
    {"action_type": "code_proposed", "description": "Proposed improvement in enrichment: Parallelize owner lookup across county scrapers with connection pooling",
     "details": {"area": "enrichment", "rationale": "Sequential county lookups bottleneck at 2 leads/sec"}, "impact_score": 0.83},
    {"action_type": "code_proposed", "description": "Proposed improvement in testing: Add integration tests for memory engine CRUD and FTS5 search",
     "details": {"area": "testing", "rationale": "Memory engine is critical path with zero test coverage"}, "impact_score": 0.81},
    {"action_type": "code_proposed", "description": "Proposed improvement in plugin_engine: Add sandboxed execution environment for untrusted plugins",
     "details": {"area": "plugin_engine", "rationale": "Arbitrary code execution from plugins is a security risk"}, "impact_score": 0.86},
    {"action_type": "code_proposed", "description": "Proposed improvement in money_engine: Integrate real-time pricing data from public market APIs",
     "details": {"area": "money_engine", "rationale": "Static pricing assumptions drift over time"}, "impact_score": 0.67},
]


# ── Memory Entries ─────────────────────────────────────────────

MEMORIES = [
    # Finance/investing (15)
    ("Compound interest is the most powerful force in wealth building — even 7% annual returns double capital every 10 years.", MemoryType.FACT, ["finance", "investing", "compound-interest"]),
    ("Index funds outperform 90% of actively managed funds over 15+ year periods due to lower fees and market-tracking efficiency.", MemoryType.FACT, ["finance", "investing", "index-funds"]),
    ("Dollar-cost averaging reduces timing risk by spreading purchases across regular intervals regardless of price.", MemoryType.LEARNING, ["finance", "investing", "DCA"]),
    ("An emergency fund of 3-6 months expenses should be liquid (high-yield savings) before any investment allocation.", MemoryType.FACT, ["finance", "emergency-fund", "personal-finance"]),
    ("Tax-loss harvesting can offset capital gains and reduce tax liability by up to $3,000/year against ordinary income.", MemoryType.FACT, ["finance", "tax-strategy", "investing"]),
    ("Passive income streams (dividends, rental, royalties) compound because they generate returns without additional time input.", MemoryType.LEARNING, ["finance", "passive-income", "wealth"]),
    ("SaaS metrics: healthy LTV/CAC ratio is 3:1 or higher; payback period under 12 months indicates strong unit economics.", MemoryType.FACT, ["finance", "SaaS", "metrics"]),
    ("ARR (Annual Recurring Revenue) is the gold standard SaaS metric — multiply MRR by 12, exclude one-time fees.", MemoryType.FACT, ["finance", "SaaS", "ARR"]),
    ("Churn rate above 5% monthly is a red flag; best SaaS companies achieve under 2% monthly churn with net negative revenue churn.", MemoryType.FACT, ["finance", "SaaS", "churn"]),
    ("LTV (Lifetime Value) = ARPU / churn rate. A $100/mo customer with 3% monthly churn has LTV of $3,333.", MemoryType.FACT, ["finance", "SaaS", "LTV"]),
    ("CAC (Customer Acquisition Cost) includes all sales and marketing spend divided by new customers acquired in that period.", MemoryType.FACT, ["finance", "SaaS", "CAC"]),
    ("Burn rate = monthly cash outflow minus inflow. Runway = cash on hand / burn rate. Under 6 months runway is danger zone.", MemoryType.FACT, ["finance", "startup", "burn-rate"]),
    ("Unit economics must be positive before scaling — negative unit economics at scale just means losing money faster.", MemoryType.LEARNING, ["finance", "startup", "unit-economics"]),
    ("Free cash flow is more important than profit — profitable companies die from cash flow mismanagement.", MemoryType.LEARNING, ["finance", "cash-flow", "business"]),
    ("The Rule of 40: a SaaS company's growth rate + profit margin should exceed 40% for healthy performance.", MemoryType.FACT, ["finance", "SaaS", "rule-of-40"]),

    # Technology/AI (15)
    ("Transformer architecture uses self-attention to weigh token relationships in parallel, replacing sequential RNN processing.", MemoryType.FACT, ["AI", "transformers", "architecture"]),
    ("RAG (Retrieval-Augmented Generation) grounds LLM responses in factual documents, reducing hallucination by 40-60%.", MemoryType.FACT, ["AI", "RAG", "LLM"]),
    ("Fine-tuning adapts a pretrained model to a specific domain using labeled examples — effective with as few as 100 high-quality samples.", MemoryType.FACT, ["AI", "fine-tuning", "ML"]),
    ("Embeddings map text to dense vectors where semantic similarity corresponds to geometric proximity in high-dimensional space.", MemoryType.FACT, ["AI", "embeddings", "NLP"]),
    ("Vector databases (Pinecone, Weaviate, Chroma) enable millisecond-latency similarity search across millions of embeddings.", MemoryType.FACT, ["AI", "vector-db", "infrastructure"]),
    ("Prompt engineering is about structuring inputs to maximize LLM output quality — system prompts, few-shot examples, and chain-of-thought.", MemoryType.LEARNING, ["AI", "prompt-engineering", "LLM"]),
    ("Agent architectures use observe-think-act loops where the LLM decides which tool to call based on current state and goal.", MemoryType.FACT, ["AI", "agents", "architecture"]),
    ("Tool use extends LLM capabilities beyond text generation — code execution, API calls, file operations, web search.", MemoryType.FACT, ["AI", "tool-use", "agents"]),
    ("Function calling in LLMs uses structured JSON schemas so the model can invoke external functions with typed parameters.", MemoryType.FACT, ["AI", "function-calling", "API"]),
    ("MCP (Model Context Protocol) standardizes how AI models connect to external tools and data sources via a unified interface.", MemoryType.FACT, ["AI", "MCP", "protocol"]),
    ("Context windows limit how much text an LLM can process at once — Claude supports 200K tokens, GPT-4o supports 128K.", MemoryType.FACT, ["AI", "context-window", "LLM"]),
    ("Tokenization splits text into subword units — 'unhappiness' might become ['un', 'happi', 'ness']. Average: 1 token per 4 characters in English.", MemoryType.FACT, ["AI", "tokenization", "NLP"]),
    ("RLHF (Reinforcement Learning from Human Feedback) aligns model outputs with human preferences using reward models.", MemoryType.FACT, ["AI", "RLHF", "alignment"]),
    ("Few-shot learning provides 2-5 examples in the prompt to teach the model a pattern without any fine-tuning.", MemoryType.LEARNING, ["AI", "few-shot", "prompt-engineering"]),
    ("Chain-of-thought prompting improves reasoning accuracy by 20-40% by asking the model to show its reasoning steps.", MemoryType.FACT, ["AI", "chain-of-thought", "reasoning"]),

    # Business/marketing (15)
    ("Product-market fit exists when users actively seek out your product and would be disappointed if it disappeared.", MemoryType.LEARNING, ["business", "product-market-fit", "startup"]),
    ("Go-to-market strategy should identify the beachhead market — one narrow segment to dominate before expanding.", MemoryType.LEARNING, ["business", "GTM", "strategy"]),
    ("SEO ROI compounds over time — a page ranking #1 generates traffic for years with minimal ongoing cost.", MemoryType.FACT, ["marketing", "SEO", "content"]),
    ("Content marketing costs 62% less than outbound marketing and generates 3x more leads per dollar spent.", MemoryType.FACT, ["marketing", "content-marketing", "ROI"]),
    ("Cold outreach response rates: personalized emails get 2-5% reply rate vs 0.1% for generic blasts.", MemoryType.FACT, ["marketing", "cold-outreach", "sales"]),
    ("Lead scoring assigns numerical values to prospects based on behavior signals (page visits, downloads, email opens) and fit criteria.", MemoryType.FACT, ["marketing", "lead-scoring", "sales"]),
    ("CRM systems are only valuable if data hygiene is maintained — dirty CRM data costs companies 12% of revenue.", MemoryType.LEARNING, ["business", "CRM", "data-quality"]),
    ("Sales funnel conversion benchmarks: awareness to lead 2-5%, lead to MQL 15-20%, MQL to SQL 50%, SQL to close 20-30%.", MemoryType.FACT, ["marketing", "sales-funnel", "conversion"]),
    ("Conversion rate optimization: changing one element at a time (headline, CTA, layout) isolates what actually moves the needle.", MemoryType.LEARNING, ["marketing", "CRO", "A/B-testing"]),
    ("A/B testing requires statistical significance (typically p < 0.05 and 1000+ samples per variant) to draw valid conclusions.", MemoryType.FACT, ["marketing", "A/B-testing", "statistics"]),
    ("Value-based pricing captures 2-5x more revenue than cost-plus pricing because it aligns price with customer-perceived value.", MemoryType.LEARNING, ["business", "pricing", "strategy"]),
    ("Competitive analysis should map competitors on two axes: feature completeness vs. ease of use to find positioning gaps.", MemoryType.LEARNING, ["business", "competitive-analysis", "positioning"]),
    ("TAM/SAM/SOM: Total Addressable Market is theoretical max, Serviceable is your segment, Obtainable is realistic near-term capture.", MemoryType.FACT, ["business", "market-sizing", "strategy"]),
    ("Positioning statement formula: For [target], [product] is the [category] that [key benefit] unlike [alternative].", MemoryType.LEARNING, ["business", "positioning", "branding"]),
    ("A strong value proposition answers three questions: What do you do? For whom? Why should they care?", MemoryType.LEARNING, ["business", "value-proposition", "messaging"]),

    # Construction industry (10)
    ("Building permits are classified by type: new construction, renovation, demolition, electrical, plumbing, mechanical, and grading.", MemoryType.FACT, ["construction", "permits", "classification"]),
    ("Inspection processes follow a sequence: foundation, framing, rough-in (electrical/plumbing), insulation, drywall, final — each must pass before the next.", MemoryType.FACT, ["construction", "inspections", "process"]),
    ("General contractor licensing requirements vary by state — some require exams, bonding, insurance, and continuing education.", MemoryType.FACT, ["construction", "licensing", "GC"]),
    ("Building codes (IBC, IRC) are adopted at the state/local level with amendments — always check the local jurisdiction's adopted version.", MemoryType.FACT, ["construction", "building-codes", "compliance"]),
    ("Zoning regulations control land use (residential, commercial, industrial), setbacks, height limits, FAR, and parking requirements.", MemoryType.FACT, ["construction", "zoning", "land-use"]),
    ("Subcontractor management: use written contracts specifying scope, timeline, payment terms, insurance requirements, and change order procedures.", MemoryType.LEARNING, ["construction", "subcontractors", "management"]),
    ("Project estimation uses three methods: unit-cost (per SF), assembly-cost (by system), and detailed quantity takeoff — accuracy increases with detail.", MemoryType.FACT, ["construction", "estimation", "costs"]),
    ("Lien waivers should be collected from every sub and supplier at each payment milestone to prevent double-payment claims.", MemoryType.LEARNING, ["construction", "lien-waivers", "legal"]),
    ("Change orders are the #1 source of construction disputes — document everything in writing with cost and schedule impact before work begins.", MemoryType.LEARNING, ["construction", "change-orders", "disputes"]),
    ("OSHA safety compliance requires job site hazard analysis, PPE, fall protection above 6 feet, and documented safety training.", MemoryType.FACT, ["construction", "safety", "OSHA"]),

    # Psychology/persuasion (10)
    ("Cognitive biases are systematic deviations from rational judgment — over 180 documented biases affect human decision-making.", MemoryType.FACT, ["psychology", "cognitive-bias", "decision-making"]),
    ("Anchoring effect: the first number presented heavily influences subsequent estimates — always set the anchor in negotiations.", MemoryType.LEARNING, ["psychology", "anchoring", "negotiation"]),
    ("Social proof: people follow the actions of others under uncertainty — testimonials, user counts, and logos build trust.", MemoryType.FACT, ["psychology", "social-proof", "persuasion"]),
    ("Scarcity principle: perceived limited availability increases desirability — 'only 3 left' triggers urgency and FOMO.", MemoryType.FACT, ["psychology", "scarcity", "persuasion"]),
    ("Reciprocity: giving something valuable first (free trial, free content) creates an obligation to reciprocate with a purchase.", MemoryType.LEARNING, ["psychology", "reciprocity", "persuasion"]),
    ("Loss aversion: people feel losses 2x more intensely than equivalent gains — frame propositions in terms of what they might lose.", MemoryType.FACT, ["psychology", "loss-aversion", "behavioral-economics"]),
    ("Confirmation bias: people seek and interpret information that confirms existing beliefs — present data that aligns first, then challenge.", MemoryType.FACT, ["psychology", "confirmation-bias", "communication"]),
    ("Dunning-Kruger effect: low competence correlates with overconfidence — seek expert feedback early and often.", MemoryType.FACT, ["psychology", "dunning-kruger", "self-awareness"]),
    ("Growth mindset: believing abilities can be developed through effort leads to higher achievement than believing talent is fixed.", MemoryType.LEARNING, ["psychology", "growth-mindset", "motivation"]),
    ("Delayed gratification (marshmallow test) predicts long-term success — train yourself to choose larger later rewards over smaller immediate ones.", MemoryType.LEARNING, ["psychology", "delayed-gratification", "discipline"]),

    # Productivity (10)
    ("Pareto principle: 80% of results come from 20% of efforts — identify and double down on the highest-leverage activities.", MemoryType.LEARNING, ["productivity", "pareto", "leverage"]),
    ("Time blocking: assign specific tasks to specific time slots — protects deep work from reactive interruptions.", MemoryType.LEARNING, ["productivity", "time-blocking", "scheduling"]),
    ("Deep work requires 90+ minute uninterrupted blocks — context switching costs 25 minutes to regain full focus.", MemoryType.FACT, ["productivity", "deep-work", "focus"]),
    ("Eisenhower matrix: urgent+important (do now), important+not urgent (schedule), urgent+not important (delegate), neither (eliminate).", MemoryType.FACT, ["productivity", "eisenhower", "prioritization"]),
    ("Habit stacking: attach a new habit to an existing one ('after I pour coffee, I write for 10 minutes') for automatic triggers.", MemoryType.LEARNING, ["productivity", "habits", "behavior-design"]),
    ("Energy management > time management — schedule creative work during peak energy hours, admin during natural dips.", MemoryType.LEARNING, ["productivity", "energy", "performance"]),
    ("Decision fatigue depletes willpower throughout the day — make important decisions in the morning, automate routine choices.", MemoryType.FACT, ["productivity", "decision-fatigue", "willpower"]),
    ("Batching similar tasks (all emails at once, all calls in one block) reduces context-switching overhead by 40%.", MemoryType.LEARNING, ["productivity", "batching", "efficiency"]),
    ("Flow state requires clear goals, immediate feedback, and challenge-skill balance — typically entered after 15-20 minutes of focused work.", MemoryType.FACT, ["productivity", "flow-state", "performance"]),
    ("Weekly review cycles (plan Monday, review Friday) maintain strategic alignment and prevent drift into busywork.", MemoryType.LEARNING, ["productivity", "review-cycles", "planning"]),

    # Legal/contracts (5)
    ("NDAs should specify: definition of confidential info, exclusions, duration (typically 2-5 years), and permitted disclosures.", MemoryType.FACT, ["legal", "NDA", "contracts"]),
    ("Non-compete enforceability varies by state — California bans them entirely; most states require reasonable scope, duration, and geography.", MemoryType.FACT, ["legal", "non-compete", "employment"]),
    ("Intellectual property created during employment typically belongs to the employer — verify IP assignment clauses in any contract.", MemoryType.FACT, ["legal", "IP", "employment"]),
    ("Liability limitations in contracts cap damages — without them, a single breach could expose unlimited financial risk.", MemoryType.LEARNING, ["legal", "liability", "risk"]),
    ("Terms of service must clearly state arbitration clauses, jurisdiction, data usage policies, and termination conditions.", MemoryType.FACT, ["legal", "TOS", "compliance"]),

    # Health/wellness (5)
    ("Sleep hygiene: consistent schedule, dark/cool room, no screens 1hr before bed — 7-9 hours is optimal for cognitive performance.", MemoryType.FACT, ["health", "sleep", "performance"]),
    ("Exercise 150 min/week (moderate) improves cognitive function by 20%, reduces anxiety, and increases neuroplasticity.", MemoryType.FACT, ["health", "exercise", "cognitive"]),
    ("Nutrition: protein at every meal (0.8-1g per lb bodyweight for active people), minimize processed foods and added sugars.", MemoryType.FACT, ["health", "nutrition", "diet"]),
    ("Chronic stress elevates cortisol, impairs memory, and weakens immunity — meditation, breathwork, and nature walks are proven mitigators.", MemoryType.FACT, ["health", "stress", "management"]),
    ("Work-life boundaries: define clear start/stop times, create physical workspace separation, and protect non-work time ruthlessly.", MemoryType.LEARNING, ["health", "work-life-balance", "boundaries"]),

    # Negotiation (5)
    ("BATNA (Best Alternative to Negotiated Agreement) is your walkaway power — always know your BATNA before entering any negotiation.", MemoryType.FACT, ["negotiation", "BATNA", "strategy"]),
    ("ZOPA (Zone of Possible Agreement) is the overlap between parties' reservation prices — no ZOPA means no deal is possible.", MemoryType.FACT, ["negotiation", "ZOPA", "deal-making"]),
    ("Anchoring in negotiation: the first offer sets the reference point — make the first offer when you have good information about fair value.", MemoryType.LEARNING, ["negotiation", "anchoring", "tactics"]),
    ("Win-win framing: expand the pie before dividing it — identify multiple issues where parties have different priorities and trade across them.", MemoryType.LEARNING, ["negotiation", "win-win", "collaboration"]),
    ("Silence is a powerful negotiation tool — after making an offer, stop talking and let the other side respond first.", MemoryType.LEARNING, ["negotiation", "silence", "tactics"]),

    # Automation/systems (10)
    ("Cron jobs should include error logging, retry logic, and dead-man-switch alerts for critical scheduled tasks.", MemoryType.LEARNING, ["automation", "cron", "reliability"]),
    ("CI/CD pipelines should run tests, linting, and security scanning on every commit — deploy only after all gates pass.", MemoryType.LEARNING, ["automation", "CI/CD", "DevOps"]),
    ("Monitoring should cover the four golden signals: latency, traffic, errors, and saturation (resource utilization).", MemoryType.FACT, ["automation", "monitoring", "SRE"]),
    ("Alerting: use severity levels (critical/warning/info) with escalation policies — page for critical, Slack for warning, log for info.", MemoryType.LEARNING, ["automation", "alerting", "incident-response"]),
    ("Log aggregation (ELK, Loki, CloudWatch) enables pattern detection across services that individual server logs miss.", MemoryType.FACT, ["automation", "logging", "observability"]),
    ("Database backups: follow 3-2-1 rule — 3 copies, 2 different media, 1 offsite. Test restores regularly.", MemoryType.LEARNING, ["automation", "backups", "disaster-recovery"]),
    ("Load balancing distributes traffic across servers using round-robin, least-connections, or weighted algorithms to prevent overload.", MemoryType.FACT, ["automation", "load-balancing", "infrastructure"]),
    ("Caching strategies: cache-aside (lazy), write-through, write-behind — choose based on read/write ratio and consistency requirements.", MemoryType.FACT, ["automation", "caching", "performance"]),
    ("Message queues (RabbitMQ, SQS, Redis Streams) decouple producers from consumers, enabling async processing and load leveling.", MemoryType.FACT, ["automation", "message-queues", "architecture"]),
    ("Infrastructure as Code (Terraform, Pulumi) ensures reproducible environments — never configure servers manually in production.", MemoryType.LEARNING, ["automation", "IaC", "DevOps"]),
]


def seed_evolutions() -> int:
    """Seed evolution log entries. Returns count of new entries added."""
    # Read existing
    existing = []
    if EVOLUTION_LOG.exists():
        with open(EVOLUTION_LOG, "r") as f:
            existing = json.load(f)

    existing_descriptions = {e["description"] for e in existing}

    new_entries = []
    for entry_data in EVOLUTION_ENTRIES:
        if entry_data["description"] in existing_descriptions:
            continue
        new_entries.append({
            "id": _evo_id(),
            "action_type": entry_data["action_type"],
            "description": entry_data["description"],
            "details": entry_data["details"],
            "impact_score": entry_data["impact_score"],
            "timestamp": _rand_ts(days_back=7),
        })

    # Sort by timestamp for organic appearance
    new_entries.sort(key=lambda e: e["timestamp"])

    combined = existing + new_entries
    combined.sort(key=lambda e: e["timestamp"])

    EVOLUTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(EVOLUTION_LOG, "w") as f:
        json.dump(combined, f, indent=2)

    return len(new_entries)


def seed_memories() -> tuple[int, int]:
    """Seed knowledge memories. Returns (inserted, skipped) counts."""
    engine = MemoryEngine()
    engine.start()

    inserted = 0
    skipped = 0

    for content, mem_type, tags in MEMORIES:
        # Dedup check: first 60 chars
        prefix = content[:60].lower()
        row = engine.conn.execute(
            "SELECT id FROM memories WHERE LOWER(content) LIKE ? LIMIT 1",
            (f"{prefix}%",),
        ).fetchone()

        if row:
            skipped += 1
            continue

        confidence = round(random.uniform(0.85, 0.95), 3)
        entry = MemoryEntry(
            content=content,
            memory_type=mem_type,
            tags=tags,
            source="knowledge_seed_v2",
            confidence=confidence,
        )
        engine.store(entry)
        inserted += 1

    engine.stop()
    return inserted, skipped


def main() -> None:
    print("=" * 60)
    print("ROOT Seed: Evolutions + Knowledge Memories")
    print("=" * 60)

    # Seed evolutions
    evo_count = seed_evolutions()
    print(f"\nEvolution log: +{evo_count} new entries")

    # Read back total
    with open(EVOLUTION_LOG, "r") as f:
        total_evos = len(json.load(f))
    print(f"Evolution log total: {total_evos} entries")

    # Seed memories
    inserted, skipped = seed_memories()
    print(f"\nMemories: +{inserted} inserted, {skipped} skipped (duplicates)")

    # Get total memory stats
    engine = MemoryEngine()
    engine.start()
    stats = engine.stats()
    engine.stop()

    print(f"Memory DB total: {stats['total']} entries")
    print(f"Avg confidence: {stats['avg_confidence']}")
    print(f"By type:")
    for mtype, info in stats["by_type"].items():
        print(f"  {mtype}: {info['count']} (avg conf: {info['avg_confidence']})")

    print(f"\n{'=' * 60}")
    print("Seeding complete.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
