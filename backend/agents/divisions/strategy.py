"""Strategy Council — 20 strategic intelligence agents."""

from __future__ import annotations

from backend.models.agent import AgentCapability, AgentProfile


def _cap(name: str, desc: str) -> AgentCapability:
    return AgentCapability(name=name, description=desc)


STRATEGY_COUNCIL: list[AgentProfile] = [
    AgentProfile(
        id="vision_architect", name="Vision Architect",
        role="Strategic Vision", tier=1, connector_type="internal",
        description="Designs long-term strategic vision and roadmaps for the civilization",
        capabilities=[
            _cap("strategic_planning", "Define multi-year strategic direction"),
            _cap("forecasting", "Project future outcomes from current trajectories"),
            _cap("research", "Investigate strategic landscape and best practices"),
            _cap("scenario_simulation", "Model alternative futures for decision support"),
            _cap("decision_making", "Evaluate options and recommend optimal paths"),
        ],
    ),
    AgentProfile(
        id="future_trends", name="Future Trends Analyst",
        role="Trend Analysis", tier=2, connector_type="internal",
        description="Identifies emerging trends across technology, markets, and society",
        capabilities=[
            _cap("trend_analysis", "Detect and track emerging macro trends"),
            _cap("web_search", "Search the web for current trend signals"),
            _cap("forecasting", "Project trend trajectories and timelines"),
            _cap("data_analysis", "Analyze trend data for patterns and inflections"),
            _cap("emerging_tech", "Scan for breakthrough technologies on the horizon"),
        ],
    ),
    AgentProfile(
        id="opportunity_hunter", name="Opportunity Hunter",
        role="Opportunity Discovery", tier=2, connector_type="internal",
        description="Scans markets and industries for actionable business opportunities",
        capabilities=[
            _cap("opportunity_scan", "Discover underserved markets and niches"),
            _cap("market_research", "Research market size, growth, and dynamics"),
            _cap("web_search", "Search for real-time market and industry data"),
            _cap("competitive_intel", "Analyze competitor gaps and weaknesses"),
            _cap("financial_analysis", "Evaluate opportunity economics and ROI"),
        ],
    ),
    AgentProfile(
        id="economic_strategist", name="Economic Strategist",
        role="Economic Strategy", tier=1, connector_type="internal",
        description="Develops economic models and revenue strategies for the civilization",
        capabilities=[
            _cap("financial_analysis", "Build financial models and projections"),
            _cap("strategic_planning", "Design revenue architecture and pricing"),
            _cap("forecasting", "Forecast revenue, costs, and growth curves"),
            _cap("risk_assessment", "Assess financial and economic risks"),
            _cap("market_research", "Research economic conditions and market forces"),
        ],
    ),
    AgentProfile(
        id="risk_strategist", name="Risk Strategist",
        role="Risk Management", tier=1, connector_type="internal",
        description="Evaluates systemic risks and designs mitigation strategies",
        capabilities=[
            _cap("risk_assessment", "Quantify and prioritize strategic risks"),
            _cap("risk_modeling", "Build probabilistic risk models"),
            _cap("scenario_simulation", "Simulate worst-case and stress scenarios"),
            _cap("research", "Investigate historical risk events and patterns"),
            _cap("decision_making", "Recommend risk-adjusted courses of action"),
        ],
    ),
    AgentProfile(
        id="innovation_designer", name="Innovation Designer",
        role="Innovation", tier=2, connector_type="internal",
        description="Generates novel product and service concepts from cross-domain insights",
        capabilities=[
            _cap("research", "Research innovation frameworks and case studies"),
            _cap("web_search", "Search for cutting-edge product concepts"),
            _cap("trend_analysis", "Identify innovation-ready trend convergences"),
            _cap("opportunity_scan", "Spot whitespace for novel solutions"),
            _cap("strategic_planning", "Design innovation roadmaps and pipelines"),
        ],
    ),
    AgentProfile(
        id="startup_strategist", name="Startup Strategist",
        role="Startup Strategy", tier=2, connector_type="internal",
        description="Designs launch strategies for new ventures and micro-SaaS products",
        capabilities=[
            _cap("strategic_planning", "Plan go-to-market and launch sequences"),
            _cap("market_research", "Validate market demand and customer segments"),
            _cap("financial_analysis", "Model unit economics and runway projections"),
            _cap("competitive_intel", "Map competitive landscape for new ventures"),
            _cap("web_search", "Research startup playbooks and success patterns"),
        ],
    ),
    AgentProfile(
        id="product_strategist", name="Product Strategy Agent",
        role="Product Strategy", tier=2, connector_type="internal",
        description="Defines product roadmaps, features, and competitive positioning",
        capabilities=[
            _cap("strategic_planning", "Build product roadmaps and feature priorities"),
            _cap("market_research", "Research user needs and market expectations"),
            _cap("competitive_intel", "Benchmark against competing products"),
            _cap("web_search", "Search for product trends and user feedback"),
            _cap("data_analysis", "Analyze usage data and product metrics"),
        ],
    ),
    AgentProfile(
        id="competitive_intel", name="Competitive Intelligence Agent",
        role="Competitive Intelligence", tier=2, connector_type="internal",
        description="Monitors competitors and industry movements for strategic advantage",
        capabilities=[
            _cap("competitive_intel", "Track competitor activity and strategy shifts"),
            _cap("web_search", "Search for competitor news, launches, and filings"),
            _cap("research", "Deep-dive into competitor products and positioning"),
            _cap("data_collection", "Collect and organize competitive data points"),
            _cap("trend_analysis", "Identify industry-wide competitive dynamics"),
        ],
    ),
    AgentProfile(
        id="market_expansion", name="Market Expansion Strategist",
        role="Market Expansion", tier=2, connector_type="internal",
        description="Identifies and plans entry into new markets and geographies",
        capabilities=[
            _cap("market_research", "Research new market opportunities and barriers"),
            _cap("strategic_planning", "Design market entry and expansion strategies"),
            _cap("web_search", "Search for regional market data and regulations"),
            _cap("risk_assessment", "Assess market entry risks and challenges"),
            _cap("financial_analysis", "Model expansion costs and revenue potential"),
        ],
    ),
    AgentProfile(
        id="scenario_simulator", name="Scenario Simulator",
        role="Simulation", tier=2, connector_type="internal",
        description="Runs what-if scenarios and Monte Carlo simulations for strategic decisions",
        capabilities=[
            _cap("scenario_simulation", "Model multi-variable what-if scenarios"),
            _cap("risk_assessment", "Quantify outcome probabilities and downside"),
            _cap("forecasting", "Project scenario outcomes over time horizons"),
            _cap("data_analysis", "Analyze simulation results for decision support"),
        ],
    ),
    AgentProfile(
        id="strategic_synthesizer", name="Strategic Synthesizer",
        role="Strategy Synthesis", tier=1, connector_type="internal",
        description="Combines inputs from all council agents into coherent strategic plans",
        capabilities=[
            _cap("knowledge_synthesis", "Merge diverse strategic inputs into plans"),
            _cap("strategic_planning", "Formulate unified strategic recommendations"),
            _cap("summarization", "Distill complex analyses into clear summaries"),
            _cap("decision_making", "Prioritize actions and resolve trade-offs"),
        ],
    ),
    AgentProfile(
        id="decision_architect", name="Decision Architect",
        role="Decision Framework", tier=1, connector_type="internal",
        description="Designs decision frameworks and evaluates trade-offs for major choices",
        capabilities=[
            _cap("decision_making", "Build decision matrices and scoring models"),
            _cap("risk_assessment", "Evaluate downside and reversibility of choices"),
            _cap("scenario_simulation", "Test decisions against multiple futures"),
            _cap("data_analysis", "Analyze quantitative inputs for decisions"),
            _cap("comparison", "Compare alternatives using structured frameworks"),
        ],
    ),
    AgentProfile(
        id="long_term_planner", name="Long-Term Planner",
        role="Long-Term Planning", tier=1, connector_type="internal",
        description="Creates multi-year plans with milestones and checkpoint evaluations",
        capabilities=[
            _cap("strategic_planning", "Create phased multi-year strategic plans"),
            _cap("forecasting", "Project long-horizon outcomes and dependencies"),
            _cap("research", "Study long-term planning best practices"),
            _cap("risk_assessment", "Identify long-range risks and contingencies"),
            _cap("decision_making", "Set milestone criteria and go/no-go gates"),
        ],
    ),
    AgentProfile(
        id="philosophy_agent", name="Philosophy Agent",
        role="Philosophical Advisor", tier=2, connector_type="internal",
        description="Provides philosophical frameworks for ethical decisions and existential questions",
        capabilities=[
            _cap("research", "Research philosophical frameworks and ethics literature"),
            _cap("analysis", "Apply ethical reasoning to strategic dilemmas"),
            _cap("decision_making", "Advise on value-aligned decision-making"),
            _cap("web_search", "Search for contemporary ethical discourse"),
        ],
    ),
    AgentProfile(
        id="geopolitical_analyst", name="Geopolitical Analyst",
        role="Geopolitical Analysis", tier=2, connector_type="internal",
        description="Analyzes geopolitical events, power shifts, and regional dynamics for strategic positioning",
        capabilities=[
            _cap("research", "Research geopolitical events, alliances, and tensions"),
            _cap("web_search", "Track news on trade policy, sanctions, and regional conflicts"),
            _cap("risk_assessment", "Assess geopolitical risk exposure for business and investments"),
            _cap("forecasting", "Project geopolitical trend trajectories and flashpoints"),
            _cap("data_analysis", "Analyze political stability indices and risk ratings"),
        ],
        metadata={"priority": 2},
    ),
    AgentProfile(
        id="regulatory_tracker", name="Regulatory Tracker",
        role="Regulatory Intelligence", tier=2, connector_type="internal",
        description="Monitors regulatory changes, compliance requirements, and legislative developments",
        capabilities=[
            _cap("web_search", "Search for new regulations, rulings, and policy announcements"),
            _cap("research", "Analyze regulatory impact on operations and strategy"),
            _cap("risk_assessment", "Quantify compliance risk from regulatory shifts"),
            _cap("summarization", "Produce regulatory change briefings and action plans"),
            _cap("trend_analysis", "Track regulatory direction across jurisdictions"),
        ],
        metadata={"priority": 2},
    ),
    AgentProfile(
        id="macro_trend_forecaster", name="Macro Trend Forecaster",
        role="Macro Forecasting", tier=2, connector_type="internal",
        description="Forecasts macro-level trends in technology, economy, and society over 3-10 year horizons",
        capabilities=[
            _cap("forecasting", "Build long-horizon macro trend forecasts"),
            _cap("trend_analysis", "Identify megatrends and structural shifts"),
            _cap("research", "Research cross-domain macro indicators"),
            _cap("data_analysis", "Analyze historical trend data for pattern extrapolation"),
            _cap("scenario_simulation", "Model multiple macro futures and their implications"),
        ],
        metadata={"priority": 2},
    ),
    AgentProfile(
        id="scenario_planner", name="Scenario Planner",
        role="Scenario Planning", tier=1, connector_type="internal",
        description="Develops structured scenario plans for strategic uncertainty and disruption preparedness",
        capabilities=[
            _cap("scenario_simulation", "Create structured plausible future scenarios"),
            _cap("strategic_planning", "Develop adaptive strategies for each scenario"),
            _cap("risk_assessment", "Identify strategic risks unique to each scenario"),
            _cap("decision_making", "Build decision triggers for scenario transitions"),
            _cap("research", "Research historical precedents for analogous scenarios"),
        ],
        metadata={"priority": 1},
    ),
    AgentProfile(
        id="stakeholder_mapper", name="Stakeholder Mapper",
        role="Stakeholder Intelligence", tier=2, connector_type="internal",
        description="Maps stakeholder ecosystems, influence networks, and relationship dynamics",
        capabilities=[
            _cap("research", "Research stakeholder backgrounds, interests, and positions"),
            _cap("web_search", "Search for stakeholder activity, partnerships, and statements"),
            _cap("data_collection", "Build structured stakeholder maps and influence graphs"),
            _cap("risk_assessment", "Assess stakeholder risk and alignment gaps"),
            _cap("strategic_planning", "Design stakeholder engagement and influence strategies"),
        ],
        metadata={"priority": 2},
    ),
]
