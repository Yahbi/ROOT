"""Engineering Division — 30 software engineering agents."""

from __future__ import annotations

from backend.models.agent import AgentCapability, AgentProfile


def _cap(name: str, desc: str) -> AgentCapability:
    return AgentCapability(name=name, description=desc)


ENGINEERING_DIVISION: list[AgentProfile] = [
    AgentProfile(
        id="chief_architect", name="Chief Software Architect",
        role="Architecture", tier=1, connector_type="internal",
        description="Designs system architecture and technical strategy",
        capabilities=[
            _cap("architecture", "Design system architecture and component topology"),
            _cap("code_review", "Review architectural decisions and code structure"),
            _cap("optimization", "Identify architectural bottlenecks and improvements"),
            _cap("documentation", "Produce architecture decision records"),
        ],
    ),
    AgentProfile(
        id="backend_eng", name="Backend Engineer",
        role="Backend Development", tier=2, connector_type="internal",
        description="Develops backend services, APIs, and server-side logic",
        capabilities=[
            _cap("backend_dev", "Build backend services and business logic"),
            _cap("code_generation", "Generate server-side code and modules"),
            _cap("debugging", "Diagnose and fix backend issues"),
            _cap("testing", "Write unit and integration tests for services"),
            _cap("database_design", "Design schemas and data access layers"),
        ],
    ),
    AgentProfile(
        id="frontend_eng", name="Frontend Engineer",
        role="Frontend Development", tier=2, connector_type="internal",
        description="Builds user interfaces and frontend applications",
        capabilities=[
            _cap("frontend_dev", "Build responsive UIs and SPAs"),
            _cap("code_generation", "Generate frontend components and pages"),
            _cap("debugging", "Debug rendering and state issues"),
            _cap("testing", "Write component and e2e tests"),
        ],
    ),
    AgentProfile(
        id="devops_eng", name="DevOps Engineer",
        role="DevOps", tier=2, connector_type="internal",
        description="Manages CI/CD pipelines, deployments, and infrastructure automation",
        capabilities=[
            _cap("devops", "Manage DevOps tooling and workflows"),
            _cap("ci_cd", "Build and maintain CI/CD pipelines"),
            _cap("deployment", "Automate and manage deployments"),
            _cap("automation", "Automate infrastructure provisioning"),
            _cap("scripting", "Write deployment and utility scripts"),
        ],
    ),
    AgentProfile(
        id="infra_eng", name="Infrastructure Engineer",
        role="Infrastructure", tier=2, connector_type="internal",
        description="Manages servers, databases, and cloud infrastructure",
        capabilities=[
            _cap("infrastructure", "Provision and manage infrastructure"),
            _cap("monitoring", "Set up infrastructure monitoring"),
            _cap("automation", "Automate infra operations"),
            _cap("security_engineering", "Harden infrastructure security"),
        ],
    ),
    AgentProfile(
        id="api_builder", name="API Builder",
        role="API Development", tier=2, connector_type="internal",
        description="Designs and implements RESTful and GraphQL APIs",
        capabilities=[
            _cap("backend_dev", "Implement API endpoints and middleware"),
            _cap("code_generation", "Generate API boilerplate and routes"),
            _cap("documentation", "Produce OpenAPI specs and API docs"),
            _cap("testing", "Write API contract and integration tests"),
        ],
    ),
    AgentProfile(
        id="db_architect", name="Database Architect",
        role="Database Design", tier=2, connector_type="internal",
        description="Designs database schemas, optimizes queries, and manages data stores",
        capabilities=[
            _cap("database_design", "Design relational and NoSQL schemas"),
            _cap("optimization", "Optimize queries and indexes"),
            _cap("backend_dev", "Implement data access layers"),
            _cap("code_review", "Review migration scripts and data models"),
        ],
    ),
    AgentProfile(
        id="microservice_arch", name="Microservice Architect",
        role="Microservices", tier=2, connector_type="internal",
        description="Designs microservice architectures and service mesh topologies",
        capabilities=[
            _cap("architecture", "Design microservice boundaries and contracts"),
            _cap("backend_dev", "Implement service communication patterns"),
            _cap("deployment", "Manage service orchestration and discovery"),
            _cap("monitoring", "Design distributed tracing and health checks"),
        ],
    ),
    AgentProfile(
        id="cloud_architect", name="Cloud Architect",
        role="Cloud Architecture", tier=2, connector_type="internal",
        description="Designs cloud-native architectures across AWS, GCP, Azure",
        capabilities=[
            _cap("architecture", "Design cloud-native system topologies"),
            _cap("infrastructure", "Provision cloud resources and networks"),
            _cap("security_engineering", "Implement cloud security controls"),
            _cap("optimization", "Optimize cloud cost and performance"),
        ],
    ),
    AgentProfile(
        id="security_eng", name="Security Engineer",
        role="Security Engineering", tier=1, connector_type="internal",
        description="Implements security controls, encryption, and access management",
        capabilities=[
            _cap("security_engineering", "Implement auth, encryption, and access controls"),
            _cap("code_review", "Audit code for security vulnerabilities"),
            _cap("testing", "Run security test suites and pen-test scripts"),
            _cap("debugging", "Investigate and remediate security incidents"),
            _cap("documentation", "Write security policies and runbooks"),
        ],
    ),
    AgentProfile(
        id="code_refactorer", name="Code Refactor Agent",
        role="Code Quality", tier=2, connector_type="internal",
        description="Refactors code for readability, performance, and maintainability",
        capabilities=[
            _cap("code_review", "Analyze code quality and tech debt"),
            _cap("optimization", "Improve performance via refactoring"),
            _cap("code_generation", "Rewrite modules with cleaner patterns"),
            _cap("testing", "Ensure refactored code passes tests"),
        ],
    ),
    AgentProfile(
        id="perf_optimizer", name="Performance Optimizer",
        role="Performance", tier=2, connector_type="internal",
        description="Profiles and optimizes application performance and resource usage",
        capabilities=[
            _cap("optimization", "Profile and eliminate bottlenecks"),
            _cap("debugging", "Diagnose latency and memory issues"),
            _cap("monitoring", "Instrument performance metrics"),
            _cap("code_review", "Review code for performance anti-patterns"),
        ],
    ),
    AgentProfile(
        id="test_engineer", name="Testing Engineer",
        role="Testing", tier=2, connector_type="internal",
        description="Writes and maintains unit, integration, and e2e test suites",
        capabilities=[
            _cap("testing", "Write and maintain comprehensive test suites"),
            _cap("code_generation", "Generate test fixtures and mocks"),
            _cap("debugging", "Diagnose flaky and failing tests"),
            _cap("automation", "Automate test execution and reporting"),
            _cap("code_review", "Review test coverage and quality"),
        ],
    ),
    AgentProfile(
        id="cicd_manager", name="CI/CD Manager",
        role="CI/CD", tier=2, connector_type="internal",
        description="Manages continuous integration and deployment pipelines",
        capabilities=[
            _cap("ci_cd", "Build and optimize CI/CD pipelines"),
            _cap("automation", "Automate build, test, and release steps"),
            _cap("deployment", "Manage release trains and versioning"),
            _cap("monitoring", "Monitor pipeline health and durations"),
        ],
    ),
    AgentProfile(
        id="deployment_mgr", name="Deployment Manager",
        role="Deployment", tier=2, connector_type="internal",
        description="Manages deployment processes, rollbacks, and blue-green deployments",
        capabilities=[
            _cap("deployment", "Execute and manage production deployments"),
            _cap("automation", "Automate rollback and canary procedures"),
            _cap("monitoring", "Track deployment health and rollout status"),
            _cap("scripting", "Write deployment automation scripts"),
        ],
    ),
    AgentProfile(
        id="monitoring_eng", name="Monitoring Engineer",
        role="Monitoring", tier=2, connector_type="internal",
        description="Sets up monitoring, alerting, and observability infrastructure",
        capabilities=[
            _cap("monitoring", "Design monitoring dashboards and alerts"),
            _cap("infrastructure", "Deploy observability stacks"),
            _cap("debugging", "Triage alerts and diagnose incidents"),
            _cap("automation", "Automate alert routing and escalation"),
        ],
    ),
    AgentProfile(
        id="logging_eng", name="Logging Engineer",
        role="Logging", tier=2, connector_type="internal",
        description="Designs logging infrastructure and log analysis pipelines",
        capabilities=[
            _cap("monitoring", "Build log aggregation and search systems"),
            _cap("infrastructure", "Deploy logging infrastructure"),
            _cap("debugging", "Analyze logs to diagnose issues"),
            _cap("optimization", "Optimize log volume and retention"),
        ],
    ),
    AgentProfile(
        id="sre_agent", name="System Reliability Engineer",
        role="SRE", tier=1, connector_type="internal",
        description="Ensures system reliability, manages SLOs, and incident response",
        capabilities=[
            _cap("system_reliability", "Define and enforce SLOs and error budgets"),
            _cap("monitoring", "Maintain observability and alerting"),
            _cap("debugging", "Lead incident response and root cause analysis"),
            _cap("automation", "Automate toil reduction and self-healing"),
            _cap("infrastructure", "Manage capacity planning and scaling"),
        ],
    ),
    AgentProfile(
        id="dep_manager", name="Dependency Manager",
        role="Dependencies", tier=2, connector_type="internal",
        description="Manages package dependencies, updates, and security patches",
        capabilities=[
            _cap("dependency_management", "Track and update package dependencies"),
            _cap("security_engineering", "Identify and patch vulnerable dependencies"),
            _cap("testing", "Verify compatibility after dependency updates"),
            _cap("automation", "Automate dependency update workflows"),
        ],
    ),
    AgentProfile(
        id="oss_integrator", name="Open Source Integrator",
        role="Open Source", tier=2, connector_type="internal",
        description="Evaluates and integrates open source tools and libraries",
        capabilities=[
            _cap("code_review", "Evaluate OSS quality and license compliance"),
            _cap("backend_dev", "Integrate libraries into the codebase"),
            _cap("testing", "Validate OSS integrations with test suites"),
            _cap("documentation", "Document OSS usage and configuration"),
        ],
    ),
    AgentProfile(
        id="automation_eng", name="Automation Engineer",
        role="Automation", tier=2, connector_type="internal",
        description="Builds automation workflows and eliminates repetitive tasks",
        capabilities=[
            _cap("automation", "Design and implement automation workflows"),
            _cap("scripting", "Write task automation scripts"),
            _cap("code_generation", "Generate boilerplate and glue code"),
            _cap("testing", "Test automation reliability and idempotency"),
        ],
    ),
    AgentProfile(
        id="tool_builder", name="Tool Builder",
        role="Tooling", tier=2, connector_type="internal",
        description="Creates internal tools, CLIs, and developer utilities",
        capabilities=[
            _cap("code_generation", "Build CLI tools and developer utilities"),
            _cap("backend_dev", "Implement tool backend logic"),
            _cap("testing", "Write tool test suites"),
            _cap("documentation", "Produce tool usage guides"),
        ],
    ),
    AgentProfile(
        id="plugin_dev", name="Plugin Developer",
        role="Plugin Development", tier=2, connector_type="internal",
        description="Develops plugins and extensions for the ROOT platform",
        capabilities=[
            _cap("plugin_dev", "Develop ROOT plugins and extensions"),
            _cap("code_generation", "Generate plugin scaffolding and hooks"),
            _cap("testing", "Test plugin integration and isolation"),
            _cap("documentation", "Write plugin API docs and guides"),
        ],
    ),
    AgentProfile(
        id="ux_engineer", name="UX Engineer",
        role="UX Engineering", tier=2, connector_type="internal",
        description="Implements user experience designs with accessibility and usability",
        capabilities=[
            _cap("frontend_dev", "Implement UX designs as interactive components"),
            _cap("code_review", "Audit UI for accessibility and usability"),
            _cap("testing", "Write accessibility and usability tests"),
            _cap("optimization", "Optimize perceived performance and load times"),
        ],
    ),
    AgentProfile(
        id="doc_engineer", name="Documentation Engineer",
        role="Documentation", tier=2, connector_type="internal",
        description="Creates and maintains technical documentation and API docs",
        capabilities=[
            _cap("documentation", "Write technical docs and API references"),
            _cap("code_review", "Review code comments and docstrings"),
            _cap("code_generation", "Generate doc site scaffolding"),
            _cap("automation", "Automate doc builds and publishing"),
        ],
    ),
    AgentProfile(
        id="code_reviewer_eng", name="Code Reviewer",
        role="Code Review", tier=2, connector_type="internal",
        description="Reviews code changes for quality, security, and best practices",
        capabilities=[
            _cap("code_review", "Review PRs for correctness and style"),
            _cap("security_engineering", "Flag security issues in code changes"),
            _cap("testing", "Verify adequate test coverage in PRs"),
            _cap("optimization", "Spot performance regressions in diffs"),
        ],
    ),
    AgentProfile(
        id="script_gen", name="Script Generator",
        role="Scripting", tier=2, connector_type="internal",
        description="Generates scripts for automation, data processing, and system tasks",
        capabilities=[
            _cap("scripting", "Generate bash, Python, and utility scripts"),
            _cap("automation", "Automate data processing and system tasks"),
            _cap("code_generation", "Produce one-off and reusable scripts"),
            _cap("testing", "Validate script output and error handling"),
        ],
    ),
    AgentProfile(
        id="api_integrator", name="API Integration Agent",
        role="API Integration", tier=2, connector_type="internal",
        description="Integrates third-party APIs and manages API connections",
        capabilities=[
            _cap("backend_dev", "Build API client libraries and wrappers"),
            _cap("code_generation", "Generate API integration boilerplate"),
            _cap("testing", "Write integration tests for external APIs"),
            _cap("debugging", "Diagnose API connectivity and auth issues"),
            _cap("documentation", "Document API integration patterns"),
        ],
    ),
    AgentProfile(
        id="framework_integrator", name="Framework Integration Agent",
        role="Framework Integration", tier=2, connector_type="internal",
        description="Integrates AI frameworks like LangChain, CrewAI, AutoGen",
        capabilities=[
            _cap("backend_dev", "Integrate AI frameworks into ROOT"),
            _cap("architecture", "Design agent framework abstractions"),
            _cap("code_generation", "Generate framework adapter code"),
            _cap("testing", "Test framework integration reliability"),
        ],
    ),
    AgentProfile(
        id="ai_model_integrator", name="AI Model Integration Agent",
        role="Model Integration", tier=2, connector_type="internal",
        description="Integrates and deploys AI models for production use",
        capabilities=[
            _cap("backend_dev", "Build model serving endpoints"),
            _cap("deployment", "Deploy and version AI models"),
            _cap("optimization", "Optimize model inference latency and cost"),
            _cap("monitoring", "Monitor model performance and drift"),
        ],
    ),
]
