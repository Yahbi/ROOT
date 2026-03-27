"""Data & Memory Division — 15 data and knowledge infrastructure agents."""

from __future__ import annotations

from backend.models.agent import AgentCapability, AgentProfile


def _cap(name: str, desc: str) -> AgentCapability:
    return AgentCapability(name=name, description=desc)


DATA_DIVISION: list[AgentProfile] = [
    AgentProfile(
        id="dataset_builder", name="Dataset Builder",
        role="Data Creation", tier=2, connector_type="internal",
        description="Creates, curates, and validates datasets for training and analysis",
        capabilities=[
            _cap("data_pipeline", "Build pipelines that produce clean datasets"),
            _cap("data_quality", "Validate schema, completeness, and correctness"),
            _cap("automation", "Automate dataset refresh and versioning"),
            _cap("documentation", "Document dataset schemas and lineage"),
        ],
    ),
    AgentProfile(
        id="kg_architect", name="Knowledge Graph Architect",
        role="Knowledge Graphs", tier=2, connector_type="internal",
        description="Builds and maintains knowledge graphs for structured reasoning",
        capabilities=[
            _cap("knowledge_graphs", "Design ontologies and graph schemas"),
            _cap("indexing", "Index entities and relationships for fast traversal"),
            _cap("data_quality", "Enforce consistency and link accuracy"),
            _cap("data_pipeline", "Ingest and transform data into graph form"),
        ],
    ),
    AgentProfile(
        id="vector_db_mgr", name="Vector Database Manager",
        role="Vector Storage", tier=2, connector_type="internal",
        description="Manages vector databases for semantic search and retrieval",
        capabilities=[
            _cap("indexing", "Build and tune vector indexes"),
            _cap("information_retrieval", "Execute semantic similarity searches"),
            _cap("optimization", "Optimize embedding dimensions and quantization"),
            _cap("monitoring", "Track index size, latency, and recall"),
        ],
    ),
    AgentProfile(
        id="semantic_indexer", name="Semantic Index Builder",
        role="Indexing", tier=2, connector_type="internal",
        description="Builds semantic indexes for fast information retrieval",
        capabilities=[
            _cap("indexing", "Build full-text and semantic indexes"),
            _cap("information_retrieval", "Optimize retrieval precision and recall"),
            _cap("optimization", "Tune index parameters for speed and accuracy"),
            _cap("data_pipeline", "Feed data through indexing pipelines"),
        ],
    ),
    AgentProfile(
        id="data_pipeline_eng", name="Data Pipeline Engineer",
        role="Data Pipelines", tier=2, connector_type="internal",
        description="Builds ETL/ELT pipelines for data processing and transformation",
        capabilities=[
            _cap("data_pipeline", "Design and implement ETL/ELT flows"),
            _cap("automation", "Schedule and orchestrate pipeline runs"),
            _cap("data_quality", "Add validation and anomaly checks to pipelines"),
            _cap("monitoring", "Monitor pipeline health and throughput"),
            _cap("scripting", "Write transformation and loading scripts"),
        ],
    ),
    AgentProfile(
        id="data_quality", name="Data Quality Monitor",
        role="Data Quality", tier=2, connector_type="internal",
        description="Monitors data quality, detects anomalies, and enforces standards",
        capabilities=[
            _cap("data_quality", "Run completeness, freshness, and accuracy checks"),
            _cap("pattern_recognition", "Detect anomalous data distributions"),
            _cap("statistical_analysis", "Compute quality metrics and thresholds"),
            _cap("automation", "Automate quality gates and alerting"),
        ],
    ),
    AgentProfile(
        id="data_compression", name="Data Compression Agent",
        role="Compression", tier=2, connector_type="internal",
        description="Optimizes data storage through compression and deduplication",
        capabilities=[
            _cap("optimization", "Compress data with optimal codec selection"),
            _cap("data_quality", "Verify lossless round-trip integrity"),
            _cap("data_pipeline", "Integrate compression into pipelines"),
            _cap("monitoring", "Track storage savings and decode latency"),
        ],
    ),
    AgentProfile(
        id="info_retrieval", name="Information Retrieval Agent",
        role="Retrieval", tier=2, connector_type="internal",
        description="Retrieves and ranks relevant information from knowledge stores",
        capabilities=[
            _cap("information_retrieval", "Search and rank documents by relevance"),
            _cap("indexing", "Maintain retrieval indexes and caches"),
            _cap("optimization", "Tune ranking models for precision"),
            _cap("data_analysis", "Analyze query patterns and click-through"),
        ],
    ),
    AgentProfile(
        id="data_annotator", name="Data Annotation Agent",
        role="Annotation", tier=2, connector_type="internal",
        description="Labels and annotates data for training and classification",
        capabilities=[
            _cap("data_quality", "Validate annotation consistency and accuracy"),
            _cap("data_pipeline", "Build annotation ingestion workflows"),
            _cap("pattern_recognition", "Suggest labels using pattern heuristics"),
            _cap("automation", "Automate bulk annotation with rules"),
        ],
    ),
    AgentProfile(
        id="insight_extractor", name="Insight Extraction Agent",
        role="Insight Extraction", tier=2, connector_type="internal",
        description="Extracts actionable insights from raw data and analysis results",
        capabilities=[
            _cap("insight_extraction", "Distill key findings from data"),
            _cap("data_analysis", "Perform exploratory data analysis"),
            _cap("statistical_analysis", "Run significance tests on findings"),
            _cap("pattern_recognition", "Spot trends and outliers in results"),
        ],
    ),
    AgentProfile(
        id="stats_agent", name="Statistics Agent",
        role="Statistics", tier=2, connector_type="internal",
        description="Performs statistical analysis, hypothesis testing, and significance tests",
        capabilities=[
            _cap("statistical_analysis", "Run hypothesis and significance tests"),
            _cap("data_analysis", "Compute descriptive and inferential statistics"),
            _cap("pattern_recognition", "Identify statistically significant patterns"),
            _cap("insight_extraction", "Summarize statistical findings"),
        ],
    ),
    AgentProfile(
        id="analytics_agent", name="Analytics Agent",
        role="Analytics", tier=2, connector_type="internal",
        description="Builds analytics dashboards and business intelligence reports",
        capabilities=[
            _cap("data_analysis", "Build analytical queries and reports"),
            _cap("insight_extraction", "Surface key business metrics"),
            _cap("statistical_analysis", "Add statistical context to dashboards"),
            _cap("automation", "Automate report generation and delivery"),
        ],
    ),
    AgentProfile(
        id="forecaster", name="Forecasting Agent",
        role="Forecasting", tier=2, connector_type="internal",
        description="Builds time-series forecasts and predictive models",
        capabilities=[
            _cap("statistical_analysis", "Fit time-series and regression models"),
            _cap("pattern_recognition", "Detect seasonality and trend components"),
            _cap("data_analysis", "Prepare and feature-engineer forecast inputs"),
            _cap("insight_extraction", "Interpret forecast confidence intervals"),
        ],
    ),
    AgentProfile(
        id="pattern_recognizer", name="Pattern Recognition Agent",
        role="Pattern Recognition", tier=2, connector_type="internal",
        description="Identifies recurring patterns in data, behavior, and markets",
        capabilities=[
            _cap("pattern_recognition", "Detect recurring and anomalous patterns"),
            _cap("signal_detection", "Surface weak signals amid noise"),
            _cap("statistical_analysis", "Validate patterns with statistical tests"),
            _cap("data_analysis", "Explore multivariate relationships"),
            _cap("insight_extraction", "Translate patterns into actionable insights"),
        ],
    ),
    AgentProfile(
        id="signal_detector", name="Signal Detection Agent",
        role="Signal Detection", tier=2, connector_type="internal",
        description="Detects weak signals in noisy data for early warning",
        capabilities=[
            _cap("signal_detection", "Detect early-warning signals in noisy data"),
            _cap("pattern_recognition", "Distinguish signal from noise"),
            _cap("statistical_analysis", "Apply filtering and detection algorithms"),
            _cap("data_analysis", "Analyze signal strength and frequency"),
        ],
    ),
]
