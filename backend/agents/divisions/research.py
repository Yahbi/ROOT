"""Research Division — 20 intelligence-gathering agents."""

from __future__ import annotations

from backend.models.agent import AgentCapability, AgentProfile


def _cap(name: str, desc: str) -> AgentCapability:
    return AgentCapability(name=name, description=desc)


RESEARCH_DIVISION: list[AgentProfile] = [
    AgentProfile(
        id="paper_miner", name="Scientific Paper Miner",
        role="Academic Research", tier=2, connector_type="internal",
        description="Extracts insights from scientific papers, ArXiv, and academic databases",
        capabilities=[
            _cap("paper_search", "Search ArXiv, Semantic Scholar, and academic DBs"),
            _cap("web_search", "Search the web for published research"),
            _cap("research", "Deep-read and analyze scientific papers"),
            _cap("summarization", "Summarize key findings and methodologies"),
            _cap("fact_checking", "Verify claims against primary sources"),
        ],
    ),
    AgentProfile(
        id="github_intel", name="GitHub Research Agent",
        role="Open Source Intelligence", tier=2, connector_type="internal",
        description="Scans GitHub for AI frameworks, tools, architectures, and trending projects",
        capabilities=[
            _cap("github_scan", "Search GitHub repos, stars, and activity"),
            _cap("web_search", "Search for open-source project discussions"),
            _cap("research", "Evaluate code quality and architecture patterns"),
            _cap("trend_analysis", "Track OSS adoption and community momentum"),
            _cap("data_collection", "Collect repo stats, contributors, and release data"),
        ],
    ),
    AgentProfile(
        id="patent_discovery", name="Patent Discovery Agent",
        role="Patent Research", tier=2, connector_type="internal",
        description="Discovers patents and IP in target domains for competitive intelligence",
        capabilities=[
            _cap("patent_search", "Search patent databases and filings"),
            _cap("web_search", "Search for patent-related news and litigation"),
            _cap("research", "Analyze patent claims and prior art"),
            _cap("data_collection", "Collect patent metadata and citation graphs"),
            _cap("summarization", "Summarize patent landscapes and key filings"),
        ],
    ),
    AgentProfile(
        id="tech_radar", name="Technology Radar",
        role="Technology Monitoring", tier=2, connector_type="internal",
        description="Maintains a technology radar tracking adoption curves and maturity",
        capabilities=[
            _cap("emerging_tech", "Track new technologies entering the market"),
            _cap("web_search", "Search for technology adoption reports"),
            _cap("trend_analysis", "Analyze technology maturity and hype cycles"),
            _cap("research", "Study technology case studies and benchmarks"),
            _cap("data_collection", "Collect adoption metrics and survey data"),
        ],
    ),
    AgentProfile(
        id="startup_scanner", name="Startup Ecosystem Analyst",
        role="Startup Analysis", tier=2, connector_type="internal",
        description="Monitors startup ecosystems, funding rounds, and emerging companies",
        capabilities=[
            _cap("web_search", "Search for funding news and startup databases"),
            _cap("research", "Analyze startup business models and traction"),
            _cap("data_collection", "Collect funding, valuation, and growth data"),
            _cap("trend_analysis", "Track startup sector trends and hot verticals"),
            _cap("competitive_intel", "Map startup competitive landscapes"),
        ],
    ),
    AgentProfile(
        id="market_researcher", name="Market Research Agent",
        role="Market Research", tier=2, connector_type="internal",
        description="Conducts market sizing, TAM analysis, and customer segment research",
        capabilities=[
            _cap("market_research", "Size markets and estimate TAM/SAM/SOM"),
            _cap("web_search", "Search for market reports and industry data"),
            _cap("data_collection", "Gather pricing, share, and growth data"),
            _cap("research", "Analyze market dynamics and buyer behavior"),
            _cap("summarization", "Produce structured market research briefs"),
        ],
    ),
    AgentProfile(
        id="academic_extractor", name="Academic Knowledge Extractor",
        role="Knowledge Extraction", tier=2, connector_type="internal",
        description="Extracts structured knowledge from academic publications and textbooks",
        capabilities=[
            _cap("paper_search", "Search academic literature and textbooks"),
            _cap("research", "Extract concepts, frameworks, and taxonomies"),
            _cap("knowledge_synthesis", "Organize extracted knowledge into structures"),
            _cap("summarization", "Distill complex academic content"),
            _cap("fact_checking", "Verify extracted facts against sources"),
        ],
    ),
    AgentProfile(
        id="data_miner", name="Data Mining Agent",
        role="Data Mining", tier=2, connector_type="internal",
        description="Discovers patterns and insights from large datasets and public data",
        capabilities=[
            _cap("data_mining", "Mine datasets for hidden patterns and signals"),
            _cap("web_search", "Search for public datasets and data portals"),
            _cap("data_collection", "Scrape and collect structured data from sources"),
            _cap("data_analysis", "Apply statistical methods to raw data"),
            _cap("summarization", "Report data mining findings and anomalies"),
        ],
    ),
    AgentProfile(
        id="knowledge_synthesizer", name="Knowledge Synthesizer",
        role="Knowledge Synthesis", tier=1, connector_type="internal",
        description="Combines knowledge from multiple research agents into unified insights",
        capabilities=[
            _cap("knowledge_synthesis", "Merge findings across research domains"),
            _cap("summarization", "Create executive-level research summaries"),
            _cap("research", "Fill knowledge gaps with targeted follow-ups"),
            _cap("fact_checking", "Cross-validate findings across sources"),
        ],
    ),
    AgentProfile(
        id="cross_domain", name="Cross-Domain Insight Agent",
        role="Cross-Domain Analysis", tier=2, connector_type="internal",
        description="Finds connections between disparate fields to generate novel insights",
        capabilities=[
            _cap("research", "Research across multiple unrelated domains"),
            _cap("knowledge_synthesis", "Connect ideas from different fields"),
            _cap("web_search", "Search for cross-disciplinary case studies"),
            _cap("trend_analysis", "Spot convergent trends across domains"),
        ],
    ),
    AgentProfile(
        id="algorithm_researcher", name="Algorithm Researcher",
        role="Algorithm R&D", tier=2, connector_type="internal",
        description="Researches algorithms, data structures, and optimization techniques",
        capabilities=[
            _cap("paper_search", "Search for algorithm papers and benchmarks"),
            _cap("research", "Analyze algorithm complexity and trade-offs"),
            _cap("web_search", "Search for implementation guides and comparisons"),
            _cap("benchmark_analysis", "Compare algorithm performance metrics"),
        ],
    ),
    AgentProfile(
        id="ai_model_researcher", name="AI Model Researcher",
        role="AI Research", tier=2, connector_type="internal",
        description="Tracks state-of-the-art AI models, benchmarks, and training techniques",
        capabilities=[
            _cap("research", "Study AI architectures and training methods"),
            _cap("benchmark_analysis", "Analyze model benchmarks and leaderboards"),
            _cap("web_search", "Search for model releases and AI news"),
            _cap("paper_search", "Search for ML/AI research papers"),
            _cap("trend_analysis", "Track AI capability progression over time"),
        ],
    ),
    AgentProfile(
        id="automation_finder", name="Automation Opportunity Finder",
        role="Automation Discovery", tier=2, connector_type="internal",
        description="Identifies processes and workflows that can be automated for revenue",
        capabilities=[
            _cap("opportunity_scan", "Spot repetitive processes ripe for automation"),
            _cap("web_search", "Search for automation tools and platforms"),
            _cap("research", "Evaluate automation feasibility and effort"),
            _cap("market_research", "Research demand for automation services"),
            _cap("data_collection", "Collect workflow data and pain point signals"),
        ],
    ),
    AgentProfile(
        id="economic_researcher", name="Economic Pattern Researcher",
        role="Economic Research", tier=2, connector_type="internal",
        description="Studies macroeconomic patterns, cycles, and their implications",
        capabilities=[
            _cap("research", "Analyze economic indicators and historical cycles"),
            _cap("web_search", "Search for economic reports and central bank data"),
            _cap("data_collection", "Gather economic time series and statistics"),
            _cap("trend_analysis", "Track macro-economic trend shifts"),
            _cap("forecasting", "Project economic conditions and impacts"),
        ],
    ),
    AgentProfile(
        id="behavior_researcher", name="Behavioral Research Agent",
        role="Behavioral Science", tier=2, connector_type="internal",
        description="Studies human behavior patterns, psychology, and decision-making biases",
        capabilities=[
            _cap("research", "Study behavioral science and psychology literature"),
            _cap("paper_search", "Search for behavioral research and experiments"),
            _cap("web_search", "Search for behavioral insights and case studies"),
            _cap("data_analysis", "Analyze behavioral data and survey results"),
            _cap("summarization", "Summarize behavioral findings for product design"),
        ],
    ),
    AgentProfile(
        id="infra_researcher", name="Infrastructure Research Agent",
        role="Infrastructure Research", tier=2, connector_type="internal",
        description="Researches cloud, compute, and infrastructure technologies and pricing",
        capabilities=[
            _cap("research", "Evaluate cloud and infrastructure solutions"),
            _cap("web_search", "Search for infrastructure pricing and benchmarks"),
            _cap("data_collection", "Collect cloud provider specs and pricing data"),
            _cap("benchmark_analysis", "Compare infrastructure performance and cost"),
            _cap("trend_analysis", "Track infrastructure technology evolution"),
        ],
    ),
    AgentProfile(
        id="security_researcher", name="Security Research Agent",
        role="Security Research", tier=2, connector_type="internal",
        description="Tracks vulnerabilities, threat intelligence, and security best practices",
        capabilities=[
            _cap("web_search", "Search for CVEs, advisories, and threat reports"),
            _cap("research", "Analyze attack vectors and defense strategies"),
            _cap("data_collection", "Collect vulnerability and threat intel feeds"),
            _cap("fact_checking", "Verify security claims and patch availability"),
            _cap("trend_analysis", "Track evolving threat landscape patterns"),
        ],
    ),
    AgentProfile(
        id="ai_benchmark", name="AI Benchmark Analyst",
        role="AI Benchmarking", tier=2, connector_type="internal",
        description="Runs and analyzes AI model benchmarks to track capability frontiers",
        capabilities=[
            _cap("benchmark_analysis", "Run and interpret AI benchmark suites"),
            _cap("web_search", "Search for latest benchmark results and rankings"),
            _cap("research", "Study benchmark methodology and validity"),
            _cap("data_collection", "Collect benchmark scores across model families"),
            _cap("summarization", "Report benchmark trends and capability gaps"),
        ],
    ),
    AgentProfile(
        id="emerging_tech", name="Emerging Technology Scout",
        role="Emerging Tech Discovery", tier=1, connector_type="internal",
        description="Discovers breakthrough technologies before they hit mainstream awareness",
        capabilities=[
            _cap("emerging_tech", "Identify pre-mainstream technology breakthroughs"),
            _cap("web_search", "Search for early-stage technology signals"),
            _cap("research", "Evaluate technology readiness and potential impact"),
            _cap("trend_analysis", "Map technology adoption curves and timelines"),
            _cap("signal_detection", "Detect weak signals of tech disruption"),
        ],
    ),
    AgentProfile(
        id="innovation_scanner", name="Innovation Scanner",
        role="Innovation Intelligence", tier=2, connector_type="internal",
        description="Scans global innovation hubs for novel ideas, products, and approaches",
        capabilities=[
            _cap("innovation_scan", "Scan innovation hubs and accelerators globally"),
            _cap("web_search", "Search for innovation news and product launches"),
            _cap("research", "Analyze innovative business models and approaches"),
            _cap("data_collection", "Collect innovation metrics and pipeline data"),
            _cap("summarization", "Produce innovation landscape reports"),
        ],
    ),
]
