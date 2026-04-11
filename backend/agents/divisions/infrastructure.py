"""Infrastructure Operations — 15 infrastructure and cloud management agents."""

from __future__ import annotations

from backend.models.agent import AgentCapability, AgentProfile


def _cap(name: str, desc: str) -> AgentCapability:
    return AgentCapability(name=name, description=desc)


INFRASTRUCTURE_OPS: list[AgentProfile] = [
    AgentProfile(
        id="compute_mgr", name="Compute Resource Manager",
        role="Compute Management", tier=2, connector_type="internal",
        description="Manages compute resources and optimizes utilization across environments",
        capabilities=[
            _cap("infrastructure", "Provision and manage compute instances"),
            _cap("monitoring", "Track CPU, memory, and GPU utilization"),
            _cap("optimization", "Right-size instances for cost and performance"),
            _cap("deployment", "Deploy workloads to appropriate compute targets"),
        ],
    ),
    AgentProfile(
        id="cloud_cost_optimizer", name="Cloud Cost Optimizer",
        role="Cost Optimization", tier=1, connector_type="internal",
        description="Optimizes cloud spending and identifies cost savings opportunities",
        capabilities=[
            _cap("cost_optimization", "Analyze and reduce cloud spending"),
            _cap("monitoring", "Track billing trends and cost anomalies"),
            _cap("infrastructure", "Recommend reserved instances and spot usage"),
            _cap("optimization", "Optimize resource allocation for cost efficiency"),
            _cap("data_analysis", "Generate cost reports and forecasts"),
        ],
    ),
    AgentProfile(
        id="server_provisioner", name="Server Provisioning Agent",
        role="Provisioning", tier=2, connector_type="internal",
        description="Provisions and configures servers, containers, and cloud instances",
        capabilities=[
            _cap("infrastructure", "Provision servers and cloud resources"),
            _cap("deployment", "Deploy infrastructure-as-code templates"),
            _cap("system_reliability", "Ensure provisioned resources meet SLA requirements"),
            _cap("monitoring", "Verify provisioned resources are healthy"),
        ],
    ),
    AgentProfile(
        id="network_monitor", name="Network Monitor",
        role="Network Monitoring", tier=2, connector_type="internal",
        description="Monitors network health, latency, and connectivity across services",
        capabilities=[
            _cap("network_monitoring", "Monitor network traffic and connectivity"),
            _cap("monitoring", "Track packet loss, jitter, and throughput"),
            _cap("health_monitoring", "Alert on network degradation and outages"),
            _cap("infrastructure", "Manage network configurations and firewall rules"),
        ],
    ),
    AgentProfile(
        id="latency_optimizer", name="Latency Optimizer",
        role="Latency Optimization", tier=2, connector_type="internal",
        description="Identifies and reduces latency across system components",
        capabilities=[
            _cap("optimization", "Profile and reduce request latency"),
            _cap("monitoring", "Measure p50, p95, p99 latency percentiles"),
            _cap("infrastructure", "Optimize CDN, caching, and routing"),
            _cap("system_reliability", "Ensure latency stays within SLA thresholds"),
        ],
    ),
    AgentProfile(
        id="backup_mgr", name="Backup Manager",
        role="Backup Management", tier=2, connector_type="internal",
        description="Manages data backups, retention policies, and recovery testing",
        capabilities=[
            _cap("backup_management", "Schedule and manage automated backups"),
            _cap("disaster_recovery", "Test backup restoration procedures"),
            _cap("monitoring", "Track backup completion and integrity"),
            _cap("system_reliability", "Ensure backup RPO and RTO compliance"),
        ],
    ),
    AgentProfile(
        id="dr_agent", name="Disaster Recovery Agent",
        role="Disaster Recovery", tier=1, connector_type="internal",
        description="Plans and executes disaster recovery procedures and failovers",
        capabilities=[
            _cap("disaster_recovery", "Design and execute DR runbooks"),
            _cap("backup_management", "Coordinate backup and restore operations"),
            _cap("infrastructure", "Manage failover infrastructure and replicas"),
            _cap("system_reliability", "Validate DR readiness through drills"),
            _cap("health_monitoring", "Monitor DR system health and replication lag"),
        ],
    ),
    AgentProfile(
        id="lb_manager", name="Load Balancer Manager",
        role="Load Balancing", tier=2, connector_type="internal",
        description="Manages load balancing, traffic distribution, and routing rules",
        capabilities=[
            _cap("infrastructure", "Configure and manage load balancers"),
            _cap("network_monitoring", "Monitor traffic patterns and distribution"),
            _cap("optimization", "Tune balancing algorithms for throughput"),
            _cap("system_reliability", "Ensure high availability through failover routing"),
        ],
    ),
    AgentProfile(
        id="infra_scaler", name="Infrastructure Scaling Agent",
        role="Scaling", tier=2, connector_type="internal",
        description="Handles auto-scaling, capacity planning, and growth readiness",
        capabilities=[
            _cap("infrastructure", "Configure auto-scaling policies and triggers"),
            _cap("monitoring", "Track resource saturation and growth trends"),
            _cap("optimization", "Balance scaling speed against cost"),
            _cap("deployment", "Roll out capacity changes safely"),
        ],
    ),
    AgentProfile(
        id="hw_monitor", name="Hardware Monitor",
        role="Hardware Monitoring", tier=2, connector_type="internal",
        description="Monitors hardware health, temperatures, disk wear, and performance",
        capabilities=[
            _cap("health_monitoring", "Track hardware vitals and degradation"),
            _cap("monitoring", "Monitor temperatures, fan speeds, and SMART data"),
            _cap("infrastructure", "Recommend hardware replacements and upgrades"),
            _cap("system_reliability", "Predict hardware failures before they occur"),
        ],
    ),
    AgentProfile(
        id="log_aggregator", name="Log Aggregator",
        role="Log Aggregation", tier=2, connector_type="internal",
        description="Aggregates logs from all services into centralized stores for search and analysis",
        capabilities=[
            _cap("monitoring", "Collect and centralize logs from all service components"),
            _cap("infrastructure", "Deploy and configure log aggregation stacks"),
            _cap("indexing", "Index log entries for fast full-text and structured search"),
            _cap("optimization", "Optimize log ingestion rates and storage costs"),
            _cap("data_analysis", "Analyze log volume trends and error rate distributions"),
        ],
        metadata={"priority": 2},
    ),
    AgentProfile(
        id="metric_collector", name="Metric Collector",
        role="Metric Collection", tier=2, connector_type="internal",
        description="Collects, stores, and manages system and business metrics across all infrastructure",
        capabilities=[
            _cap("monitoring", "Instrument services and collect time-series metrics"),
            _cap("infrastructure", "Deploy metric collection agents and exporters"),
            _cap("data_pipeline", "Build metric ingestion and aggregation pipelines"),
            _cap("optimization", "Optimize metric cardinality and storage efficiency"),
            _cap("data_analysis", "Analyze metric trends for capacity and performance insights"),
        ],
        metadata={"priority": 2},
    ),
    AgentProfile(
        id="alert_manager", name="Alert Manager",
        role="Alert Management", tier=2, connector_type="internal",
        description="Manages alerting rules, routing, silencing, and on-call escalation for all systems",
        capabilities=[
            _cap("monitoring", "Define and manage alerting rules and thresholds"),
            _cap("automation", "Route alerts to appropriate teams via PagerDuty, Slack, or SMS"),
            _cap("health_monitoring", "Suppress flapping alerts and manage maintenance windows"),
            _cap("optimization", "Tune alert signal-to-noise ratio to reduce alert fatigue"),
            _cap("system_reliability", "Ensure critical alerts reach on-call within SLA"),
        ],
        metadata={"priority": 1},
    ),
    AgentProfile(
        id="backup_validator", name="Backup Validator",
        role="Backup Validation", tier=2, connector_type="internal",
        description="Validates backup integrity through automated restore testing and checksum verification",
        capabilities=[
            _cap("backup_management", "Run automated restore drills on backup snapshots"),
            _cap("disaster_recovery", "Verify backup RPO and RTO compliance through testing"),
            _cap("data_quality", "Validate backup checksums and data completeness"),
            _cap("monitoring", "Track backup validation coverage and last-tested timestamps"),
            _cap("system_reliability", "Alert on backup failures and integrity mismatches"),
        ],
        metadata={"priority": 1},
    ),
    AgentProfile(
        id="cost_analyzer", name="Cost Analyzer",
        role="Cost Analysis", tier=2, connector_type="internal",
        description="Analyzes infrastructure costs in depth and surfaces actionable savings opportunities",
        capabilities=[
            _cap("cost_optimization", "Perform detailed cost attribution and allocation analysis"),
            _cap("data_analysis", "Identify cost anomalies and underutilized resources"),
            _cap("optimization", "Recommend reserved instances, spot usage, and right-sizing"),
            _cap("monitoring", "Track unit economics per service, feature, and customer"),
            _cap("financial_analysis", "Model cost impact of architectural and configuration changes"),
        ],
        metadata={"priority": 2},
    ),
]
