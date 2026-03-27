"""Automation Business — 10 workflow and process automation agents."""

from __future__ import annotations

from backend.models.agent import AgentCapability, AgentProfile


def _cap(name: str, desc: str) -> AgentCapability:
    return AgentCapability(name=name, description=desc)


AUTOMATION_ENGINE: list[AgentProfile] = [
    AgentProfile(
        id="lead_scraper", name="Lead Scraping Agent",
        role="Lead Scraping", tier=2, connector_type="internal",
        description="Scrapes and enriches business leads from public sources",
        capabilities=[
            _cap("lead_generation", "Discover and collect qualified business leads"),
            _cap("web_search", "Search directories, LinkedIn, and public databases"),
            _cap("data_mining", "Extract structured lead data from web pages"),
            _cap("data_analysis", "Score and rank leads by conversion potential"),
        ],
    ),
    AgentProfile(
        id="email_outreach", name="Email Outreach Agent",
        role="Email Outreach", tier=2, connector_type="internal",
        description="Manages cold email campaigns, sequences, and follow-ups",
        capabilities=[
            _cap("email_outreach", "Create and manage outbound email sequences"),
            _cap("writing", "Write persuasive cold emails and follow-ups"),
            _cap("data_analysis", "Track open rates, replies, and conversion metrics"),
            _cap("lead_generation", "Qualify leads through email engagement"),
        ],
    ),
    AgentProfile(
        id="crm_automation", name="CRM Automation Agent",
        role="CRM Automation", tier=2, connector_type="internal",
        description="Automates CRM data entry, pipeline tracking, and workflow triggers",
        capabilities=[
            _cap("crm", "Manage contacts, deals, and pipeline stages"),
            _cap("automation", "Build automated CRM workflows and triggers"),
            _cap("data_analysis", "Generate CRM reports and pipeline analytics"),
            _cap("process_optimization", "Streamline sales processes and reduce manual work"),
        ],
    ),
    AgentProfile(
        id="support_bot_builder", name="Customer Support Bot Builder",
        role="Bot Building", tier=2, connector_type="internal",
        description="Builds AI-powered customer support chatbots and knowledge bases",
        capabilities=[
            _cap("automation", "Design and deploy conversational support bots"),
            _cap("writing", "Write bot responses and knowledge base articles"),
            _cap("workflow_design", "Map customer support flows and escalation paths"),
            _cap("web_search", "Research best practices for support automation"),
        ],
    ),
    AgentProfile(
        id="workflow_architect", name="Workflow Automation Architect",
        role="Workflow Architecture", tier=2, connector_type="internal",
        description="Designs complex business workflow automations end-to-end",
        capabilities=[
            _cap("workflow_design", "Architect multi-step business workflows"),
            _cap("automation", "Build automation pipelines with error handling"),
            _cap("process_optimization", "Identify automation opportunities in processes"),
            _cap("scripting", "Write integration scripts and connectors"),
            _cap("web_search", "Research automation tools and API capabilities"),
        ],
    ),
    AgentProfile(
        id="data_extractor", name="Data Extraction Agent",
        role="Data Extraction", tier=2, connector_type="internal",
        description="Extracts structured data from websites, PDFs, and documents",
        capabilities=[
            _cap("data_mining", "Scrape and parse data from diverse sources"),
            _cap("web_search", "Locate data sources and public datasets"),
            _cap("scripting", "Write extraction scripts and parsers"),
            _cap("data_analysis", "Validate and clean extracted data"),
        ],
    ),
    AgentProfile(
        id="process_optimizer", name="Process Optimization Agent",
        role="Process Optimization", tier=2, connector_type="internal",
        description="Identifies bottlenecks and optimizes business processes",
        capabilities=[
            _cap("process_optimization", "Analyze and improve business workflows"),
            _cap("data_analysis", "Measure process performance and efficiency"),
            _cap("workflow_design", "Redesign processes for optimal throughput"),
            _cap("automation", "Automate repetitive process steps"),
        ],
    ),
    AgentProfile(
        id="automation_deployer", name="Automation Deployment Agent",
        role="Deployment", tier=2, connector_type="internal",
        description="Deploys, configures, and tests automation solutions for clients",
        capabilities=[
            _cap("automation", "Deploy automations to production environments"),
            _cap("scripting", "Write deployment and configuration scripts"),
            _cap("workflow_design", "Validate deployed workflows end-to-end"),
            _cap("web_search", "Research deployment best practices and platforms"),
        ],
    ),
    AgentProfile(
        id="automation_maintainer", name="Automation Maintenance Agent",
        role="Maintenance", tier=2, connector_type="internal",
        description="Monitors and maintains deployed automations for reliability",
        capabilities=[
            _cap("automation", "Monitor automation health and error rates"),
            _cap("process_optimization", "Tune automations for performance"),
            _cap("scripting", "Patch and update automation scripts"),
            _cap("data_analysis", "Report on automation uptime and throughput"),
        ],
    ),
    AgentProfile(
        id="automation_sales", name="Automation Sales Agent",
        role="Sales", tier=2, connector_type="internal",
        description="Sells automation services, scopes projects, and creates proposals",
        capabilities=[
            _cap("sales", "Pitch automation services and close deals"),
            _cap("web_search", "Research prospect businesses and pain points"),
            _cap("lead_generation", "Identify companies that need automation"),
            _cap("writing", "Write proposals, SOWs, and case studies"),
            _cap("data_analysis", "Build ROI projections for prospects"),
        ],
    ),
]
