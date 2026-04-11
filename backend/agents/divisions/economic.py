"""Economic Engine — 25 revenue and growth agents."""

from __future__ import annotations

from backend.models.agent import AgentCapability, AgentProfile


def _cap(name: str, desc: str) -> AgentCapability:
    return AgentCapability(name=name, description=desc)


ECONOMIC_ENGINE: list[AgentProfile] = [
    AgentProfile(
        id="opportunity_scanner", name="Opportunity Scanner",
        role="Opportunity Scanning", tier=2, connector_type="internal",
        description="Continuously scans for revenue opportunities across markets",
        capabilities=[
            _cap("opportunity_scan", "Scan markets for untapped revenue opportunities"),
            _cap("market_research", "Research market size, trends, and demand"),
            _cap("competitive_intel", "Analyze competitor positioning and gaps"),
            _cap("opportunity_scoring", "Score and rank opportunities by ROI potential"),
            _cap("web_search", "Search the web for emerging market signals"),
        ],
    ),
    AgentProfile(
        id="startup_builder", name="Startup Builder",
        role="Startup Building", tier=2, connector_type="internal",
        description="Builds and launches micro-startups and MVPs",
        capabilities=[
            _cap("startup_analysis", "Analyze startup viability and market fit"),
            _cap("market_research", "Validate demand through market research"),
            _cap("financial_analysis", "Model unit economics and runway"),
            _cap("comparison", "Compare business model alternatives"),
        ],
    ),
    AgentProfile(
        id="product_builder", name="Product Builder",
        role="Product Building", tier=2, connector_type="internal",
        description="Builds digital products from concept to launch",
        capabilities=[
            _cap("market_research", "Research user needs and product-market fit"),
            _cap("competitive_intel", "Analyze competing products and features"),
            _cap("pricing_analysis", "Determine optimal product pricing"),
            _cap("evaluation", "Evaluate product performance post-launch"),
        ],
    ),
    AgentProfile(
        id="saas_creator", name="Micro-SaaS Creator",
        role="SaaS Creation", tier=2, connector_type="internal",
        description="Creates subscription-based SaaS tools and services",
        capabilities=[
            _cap("market_research", "Identify SaaS niches with recurring demand"),
            _cap("pricing_analysis", "Design subscription pricing tiers"),
            _cap("revenue_optimization", "Optimize MRR through churn reduction"),
            _cap("financial_analysis", "Model SaaS unit economics and LTV/CAC"),
            _cap("competitive_intel", "Map the competitive SaaS landscape"),
        ],
    ),
    AgentProfile(
        id="agency_builder", name="Automation Agency Builder",
        role="Agency Building", tier=2, connector_type="internal",
        description="Builds automation agency services for business clients",
        capabilities=[
            _cap("market_research", "Research agency service demand and pricing"),
            _cap("lead_generation", "Generate leads for agency services"),
            _cap("sales", "Pitch and close agency deals"),
            _cap("pricing_analysis", "Set project and retainer pricing"),
            _cap("revenue_optimization", "Optimize agency margins and capacity"),
        ],
    ),
    AgentProfile(
        id="marketing_strategist", name="Marketing Strategist",
        role="Marketing", tier=2, connector_type="internal",
        description="Develops marketing strategies and go-to-market plans",
        capabilities=[
            _cap("market_research", "Research target audiences and channels"),
            _cap("content_marketing", "Design content-led marketing funnels"),
            _cap("social_media", "Plan social media marketing campaigns"),
            _cap("seo", "Integrate SEO into marketing strategy"),
            _cap("lead_generation", "Design lead generation campaigns"),
        ],
    ),
    AgentProfile(
        id="seo_specialist", name="SEO Specialist",
        role="SEO", tier=2, connector_type="internal",
        description="Optimizes content and sites for search engine visibility",
        capabilities=[
            _cap("seo", "Optimize on-page and technical SEO"),
            _cap("web_search", "Research keywords and SERP competition"),
            _cap("content_marketing", "Align content with search intent"),
            _cap("benchmark_analysis", "Track SEO rankings and improvements"),
        ],
    ),
    AgentProfile(
        id="content_marketer", name="Content Marketing Agent",
        role="Content Marketing", tier=2, connector_type="internal",
        description="Creates content marketing strategies and distribution plans",
        capabilities=[
            _cap("content_marketing", "Design content calendars and campaigns"),
            _cap("seo", "Optimize content for organic discovery"),
            _cap("social_media", "Distribute content across social channels"),
            _cap("web_search", "Research trending topics and content gaps"),
            _cap("market_research", "Analyze audience content preferences"),
        ],
    ),
    AgentProfile(
        id="social_growth", name="Social Media Growth Agent",
        role="Social Growth", tier=2, connector_type="internal",
        description="Grows social media presence and engagement",
        capabilities=[
            _cap("social_media", "Manage and grow social media accounts"),
            _cap("content_marketing", "Create engaging social content"),
            _cap("web_search", "Research viral trends and hashtags"),
            _cap("market_research", "Analyze audience demographics and behavior"),
        ],
    ),
    AgentProfile(
        id="ad_agent", name="Advertising Agent",
        role="Advertising", tier=2, connector_type="internal",
        description="Manages advertising campaigns across platforms",
        capabilities=[
            _cap("market_research", "Research ad platforms and audience targeting"),
            _cap("financial_analysis", "Track ad spend and ROAS metrics"),
            _cap("revenue_optimization", "Optimize ad campaigns for conversions"),
            _cap("comparison", "Compare ad creatives and platform performance"),
            _cap("pricing_analysis", "Optimize bid strategies and budgets"),
        ],
    ),
    AgentProfile(
        id="lead_gen", name="Lead Generation Agent",
        role="Lead Generation", tier=2, connector_type="internal",
        description="Generates and qualifies leads for products and services",
        capabilities=[
            _cap("lead_generation", "Generate qualified leads from multiple channels"),
            _cap("web_search", "Find prospects and contact information"),
            _cap("sales", "Score and qualify leads for sales readiness"),
            _cap("crm", "Track lead status and pipeline metrics"),
        ],
    ),
    AgentProfile(
        id="sales_outreach", name="Sales Outreach Agent",
        role="Sales", tier=2, connector_type="internal",
        description="Manages outbound sales sequences and follow-ups",
        capabilities=[
            _cap("sales", "Run outbound sales sequences and close deals"),
            _cap("lead_generation", "Convert outreach into qualified leads"),
            _cap("crm", "Log interactions and manage deal pipeline"),
            _cap("web_search", "Research prospects before outreach"),
            _cap("partnership", "Identify partnership-driven sales channels"),
        ],
    ),
    AgentProfile(
        id="crm_agent", name="CRM Automation Agent",
        role="CRM", tier=2, connector_type="internal",
        description="Automates CRM workflows and customer relationship management",
        capabilities=[
            _cap("crm", "Automate CRM data entry and workflows"),
            _cap("lead_generation", "Manage lead nurturing sequences"),
            _cap("sales", "Track deal stages and forecast pipeline"),
            _cap("evaluation", "Evaluate customer health and churn risk"),
        ],
    ),
    AgentProfile(
        id="client_success", name="Client Success Agent",
        role="Client Success", tier=2, connector_type="internal",
        description="Ensures client satisfaction, retention, and upsell opportunities",
        capabilities=[
            _cap("crm", "Monitor client health scores and engagement"),
            _cap("revenue_optimization", "Identify upsell and cross-sell opportunities"),
            _cap("sales", "Execute renewal and expansion conversations"),
            _cap("evaluation", "Evaluate client satisfaction and NPS"),
        ],
    ),
    AgentProfile(
        id="revenue_optimizer", name="Revenue Optimization Agent",
        role="Revenue Optimization", tier=2, connector_type="internal",
        description="Optimizes revenue across all streams through pricing and packaging",
        capabilities=[
            _cap("revenue_optimization", "Optimize revenue across all streams"),
            _cap("pricing_analysis", "Analyze and adjust pricing for max revenue"),
            _cap("financial_analysis", "Model revenue scenarios and projections"),
            _cap("financial_forecasting", "Forecast revenue growth trajectories"),
            _cap("benchmark_analysis", "Benchmark revenue metrics against industry"),
        ],
    ),
    AgentProfile(
        id="pricing_strategist", name="Pricing Strategist",
        role="Pricing", tier=2, connector_type="internal",
        description="Designs pricing models and competitive pricing strategies",
        capabilities=[
            _cap("pricing_analysis", "Analyze price sensitivity and willingness to pay"),
            _cap("competitive_intel", "Research competitor pricing models"),
            _cap("financial_analysis", "Model margin impact of pricing changes"),
            _cap("comparison", "Compare pricing strategies across segments"),
            _cap("market_research", "Research price anchoring and positioning"),
        ],
    ),
    AgentProfile(
        id="market_expander", name="Market Expansion Agent",
        role="Market Expansion", tier=2, connector_type="internal",
        description="Plans and executes expansion into new markets",
        capabilities=[
            _cap("market_research", "Research new market opportunities and barriers"),
            _cap("competitive_intel", "Analyze competitive landscape in new markets"),
            _cap("opportunity_scoring", "Score market expansion opportunities"),
            _cap("financial_forecasting", "Forecast revenue potential in new markets"),
        ],
    ),
    AgentProfile(
        id="affiliate_agent", name="Affiliate Network Agent",
        role="Affiliate Marketing", tier=2, connector_type="internal",
        description="Builds and manages affiliate marketing networks",
        capabilities=[
            _cap("partnership", "Recruit and manage affiliate partners"),
            _cap("revenue_optimization", "Optimize affiliate commission structures"),
            _cap("lead_generation", "Drive traffic through affiliate channels"),
            _cap("financial_analysis", "Track affiliate ROI and payouts"),
        ],
    ),
    AgentProfile(
        id="partnership_builder", name="Partnership Builder",
        role="Partnerships", tier=2, connector_type="internal",
        description="Identifies and builds strategic partnerships",
        capabilities=[
            _cap("partnership", "Build and manage strategic partnerships"),
            _cap("web_search", "Discover potential partners and integrations"),
            _cap("opportunity_scoring", "Score partnership opportunities by value"),
            _cap("sales", "Negotiate partnership terms and agreements"),
            _cap("market_research", "Research partner ecosystems and synergies"),
        ],
    ),
    AgentProfile(
        id="financial_forecaster", name="Financial Forecast Agent",
        role="Financial Forecasting", tier=2, connector_type="internal",
        description="Creates financial forecasts and budget projections",
        capabilities=[
            _cap("financial_forecasting", "Build revenue and expense forecasts"),
            _cap("financial_analysis", "Analyze financial health and trends"),
            _cap("revenue_optimization", "Identify revenue growth levers"),
            _cap("risk_assessment", "Assess financial risk and downside scenarios"),
            _cap("evaluation", "Evaluate forecast accuracy and recalibrate"),
        ],
    ),
    AgentProfile(
        id="subscription_optimizer", name="Subscription Optimizer",
        role="Subscription Optimization", tier=2, connector_type="internal",
        description="Optimizes subscription models, billing cycles, and plan structures for MRR growth",
        capabilities=[
            _cap("revenue_optimization", "Optimize subscription tier structures and billing"),
            _cap("pricing_analysis", "Analyze willingness-to-pay across subscriber segments"),
            _cap("financial_analysis", "Model MRR, ARR, and expansion revenue scenarios"),
            _cap("benchmark_analysis", "Benchmark subscription metrics against SaaS industry"),
            _cap("evaluation", "Evaluate subscription change impact on key cohort metrics"),
        ],
        metadata={"priority": 2},
    ),
    AgentProfile(
        id="churn_predictor", name="Churn Predictor",
        role="Churn Prediction", tier=2, connector_type="internal",
        description="Predicts customer churn risk and recommends proactive retention interventions",
        capabilities=[
            _cap("pattern_recognition", "Identify behavioral patterns predictive of churn"),
            _cap("statistical_analysis", "Build churn probability models from usage data"),
            _cap("data_analysis", "Analyze engagement signals and health score trends"),
            _cap("evaluation", "Evaluate model accuracy and update prediction thresholds"),
            _cap("revenue_optimization", "Prioritize retention actions by revenue at risk"),
        ],
        metadata={"priority": 1},
    ),
    AgentProfile(
        id="ltv_calculator", name="LTV Calculator",
        role="Lifetime Value Analysis", tier=2, connector_type="internal",
        description="Calculates and segments customer lifetime value to guide acquisition and retention spend",
        capabilities=[
            _cap("financial_analysis", "Compute LTV by segment, channel, and product tier"),
            _cap("statistical_analysis", "Apply cohort analysis and survival models to LTV"),
            _cap("data_analysis", "Analyze LTV drivers and correlation with usage patterns"),
            _cap("pricing_analysis", "Align pricing strategy with LTV-to-CAC targets"),
            _cap("financial_forecasting", "Forecast LTV evolution under different growth scenarios"),
        ],
        metadata={"priority": 2},
    ),
    AgentProfile(
        id="pricing_tester", name="Pricing Tester",
        role="Pricing Experimentation", tier=2, connector_type="internal",
        description="Designs and runs pricing experiments to find optimal price points and packaging",
        capabilities=[
            _cap("experiment_design", "Design controlled pricing experiments and price tests"),
            _cap("pricing_analysis", "Analyze price elasticity and conversion impact"),
            _cap("statistical_analysis", "Evaluate pricing test results with significance testing"),
            _cap("revenue_optimization", "Identify revenue-maximizing price-volume combinations"),
            _cap("competitive_intel", "Monitor competitor pricing changes and market reactions"),
        ],
        metadata={"priority": 2},
    ),
    AgentProfile(
        id="revenue_forecaster", name="Revenue Forecaster",
        role="Revenue Forecasting", tier=2, connector_type="internal",
        description="Builds granular revenue forecasts by stream, segment, and time horizon",
        capabilities=[
            _cap("financial_forecasting", "Build bottom-up and top-down revenue forecasts"),
            _cap("statistical_analysis", "Apply time-series models to revenue data"),
            _cap("data_analysis", "Analyze revenue composition by stream and cohort"),
            _cap("risk_assessment", "Quantify revenue forecast uncertainty and downside risk"),
            _cap("evaluation", "Track forecast accuracy and recalibrate models"),
        ],
        metadata={"priority": 1},
    ),
]
