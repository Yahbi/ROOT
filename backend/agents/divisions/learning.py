"""Learning & Improvement Division — 25 self-evolution agents."""

from __future__ import annotations

from backend.models.agent import AgentCapability, AgentProfile


def _cap(name: str, desc: str) -> AgentCapability:
    return AgentCapability(name=name, description=desc)


LEARNING_DIVISION: list[AgentProfile] = [
    AgentProfile(
        id="experiment_designer", name="Experiment Designer",
        role="Experiment Design", tier=2, connector_type="internal",
        description="Designs experiments to test hypotheses and strategies",
        capabilities=[
            _cap("experiment_design", "Design controlled experiments with clear metrics"),
            _cap("hypothesis_testing", "Define testable hypotheses from observations"),
            _cap("evaluation", "Evaluate experiment outcomes against baselines"),
            _cap("statistical_analysis", "Apply statistical methods to validate results"),
        ],
    ),
    AgentProfile(
        id="hypothesis_gen", name="Hypothesis Generator",
        role="Hypothesis Generation", tier=2, connector_type="internal",
        description="Generates testable hypotheses from observations and data",
        capabilities=[
            _cap("hypothesis_testing", "Formulate and structure testable hypotheses"),
            _cap("experiment_design", "Frame hypotheses as runnable experiments"),
            _cap("gap_analysis", "Identify knowledge gaps that need hypotheses"),
            _cap("reflection", "Reflect on past outcomes to generate new hypotheses"),
            _cap("pattern_recognition", "Spot patterns that suggest causal relationships"),
        ],
    ),
    AgentProfile(
        id="failure_analyst", name="Failure Analyst",
        role="Failure Analysis", tier=1, connector_type="internal",
        description="Analyzes failures to extract root causes and prevention strategies",
        capabilities=[
            _cap("self_analysis", "Analyze system behavior during failure events"),
            _cap("reflection", "Reflect on failure patterns and recurring issues"),
            _cap("gap_analysis", "Identify capability gaps exposed by failures"),
            _cap("evaluation", "Evaluate severity and impact of failure modes"),
            _cap("knowledge_expansion", "Convert failure lessons into reusable knowledge"),
        ],
    ),
    AgentProfile(
        id="pattern_extractor", name="Pattern Extractor",
        role="Pattern Extraction", tier=2, connector_type="internal",
        description="Extracts reusable patterns from successful outcomes",
        capabilities=[
            _cap("pattern_recognition", "Detect recurring success and failure patterns"),
            _cap("insight_extraction", "Extract actionable insights from raw data"),
            _cap("knowledge_expansion", "Codify patterns into shared knowledge base"),
            _cap("self_analysis", "Analyze system logs for behavioral patterns"),
        ],
    ),
    AgentProfile(
        id="learning_strategist", name="Learning Strategy Agent",
        role="Learning Strategy", tier=2, connector_type="internal",
        description="Optimizes learning paths and knowledge acquisition strategies",
        capabilities=[
            _cap("learning_strategy", "Design adaptive learning paths and curricula"),
            _cap("gap_analysis", "Identify priority knowledge gaps to fill"),
            _cap("knowledge_expansion", "Expand knowledge through targeted acquisition"),
            _cap("evaluation", "Evaluate learning effectiveness and retention"),
            _cap("reflection", "Reflect on learning progress and adjust strategy"),
        ],
    ),
    AgentProfile(
        id="prompt_optimizer", name="Prompt Optimization Agent",
        role="Prompt Engineering", tier=2, connector_type="internal",
        description="Optimizes prompts for better LLM performance and cost efficiency",
        capabilities=[
            _cap("prompt_engineering", "Engineer and refine prompts for optimal output"),
            _cap("experiment_design", "Design A/B tests for prompt variants"),
            _cap("evaluation", "Evaluate prompt quality across tasks and models"),
            _cap("benchmark_analysis", "Benchmark prompt performance against baselines"),
        ],
    ),
    AgentProfile(
        id="workflow_optimizer", name="Workflow Optimization Agent",
        role="Workflow Optimization", tier=2, connector_type="internal",
        description="Optimizes multi-agent workflows for speed and quality",
        capabilities=[
            _cap("optimization", "Optimize agent pipelines and task routing"),
            _cap("self_analysis", "Analyze workflow bottlenecks and inefficiencies"),
            _cap("benchmark_analysis", "Benchmark workflow throughput and latency"),
            _cap("evaluation", "Evaluate workflow changes against KPIs"),
            _cap("process_optimization", "Streamline multi-step processes"),
        ],
    ),
    AgentProfile(
        id="agent_auditor", name="Agent Performance Auditor",
        role="Performance Audit", tier=1, connector_type="internal",
        description="Audits agent performance, tracks quality metrics, and recommends improvements",
        capabilities=[
            _cap("self_analysis", "Audit individual agent effectiveness and costs"),
            _cap("benchmark_analysis", "Compare agent performance against benchmarks"),
            _cap("evaluation", "Evaluate agent output quality and consistency"),
            _cap("performance_metrics", "Track and report agent performance metrics"),
            _cap("gap_analysis", "Identify underperforming agents and capability gaps"),
        ],
    ),
    AgentProfile(
        id="self_improvement_planner", name="Self-Improvement Planner",
        role="Self-Improvement", tier=1, connector_type="internal",
        description="Plans and prioritizes system self-improvement initiatives",
        capabilities=[
            _cap("gap_analysis", "Identify highest-impact improvement opportunities"),
            _cap("self_analysis", "Assess current system strengths and weaknesses"),
            _cap("learning_strategy", "Design improvement roadmaps and milestones"),
            _cap("reflection", "Reflect on past improvements and their outcomes"),
            _cap("skill_creation", "Propose new skills to fill capability gaps"),
        ],
    ),
    AgentProfile(
        id="knowledge_distiller", name="Knowledge Distillation Agent",
        role="Knowledge Distillation", tier=2, connector_type="internal",
        description="Distills complex knowledge into concise, actionable summaries",
        capabilities=[
            _cap("knowledge_expansion", "Expand and enrich the knowledge base"),
            _cap("summarization", "Compress complex information into key takeaways"),
            _cap("knowledge_synthesis", "Synthesize knowledge from multiple sources"),
            _cap("insight_extraction", "Extract core insights from verbose data"),
        ],
    ),
    AgentProfile(
        id="reflection_agent", name="Reflection Agent",
        role="Reflection", tier=2, connector_type="internal",
        description="Facilitates deep self-reflection on system behavior and outcomes",
        capabilities=[
            _cap("reflection", "Guide structured self-reflection sessions"),
            _cap("self_analysis", "Analyze system decisions and their consequences"),
            _cap("evaluation", "Evaluate alignment between actions and goals"),
            _cap("learning_strategy", "Derive learning objectives from reflections"),
        ],
    ),
    AgentProfile(
        id="cognitive_strategist", name="Cognitive Strategy Agent",
        role="Cognitive Strategy", tier=2, connector_type="internal",
        description="Applies cognitive science principles to improve system reasoning",
        capabilities=[
            _cap("learning_strategy", "Apply cognitive science to learning design"),
            _cap("reflection", "Analyze reasoning quality and biases"),
            _cap("prompt_engineering", "Improve reasoning through prompt structure"),
            _cap("self_analysis", "Diagnose cognitive bottlenecks in agent behavior"),
            _cap("optimization", "Optimize reasoning chains for accuracy and speed"),
        ],
    ),
    AgentProfile(
        id="long_term_learner", name="Long-Term Learning Agent",
        role="Long-Term Learning", tier=2, connector_type="internal",
        description="Manages long-term knowledge retention and spaced repetition",
        capabilities=[
            _cap("learning_strategy", "Design long-term retention strategies"),
            _cap("knowledge_expansion", "Expand knowledge with durable encoding"),
            _cap("reflection", "Review and reinforce decaying knowledge"),
            _cap("self_analysis", "Track knowledge decay and retention rates"),
        ],
    ),
    AgentProfile(
        id="skill_developer", name="Skill Development Agent",
        role="Skill Development", tier=2, connector_type="internal",
        description="Develops new capabilities and skills for the agent civilization",
        capabilities=[
            _cap("skill_creation", "Create new SKILL.md files for the system"),
            _cap("gap_analysis", "Identify missing skills across divisions"),
            _cap("learning_strategy", "Design skill acquisition pathways"),
            _cap("evaluation", "Evaluate skill quality and coverage"),
            _cap("knowledge_expansion", "Research best practices for new skills"),
        ],
    ),
    AgentProfile(
        id="benchmark_designer", name="Benchmark Designer",
        role="Benchmark Design", tier=2, connector_type="internal",
        description="Designs benchmarks to measure system and agent capabilities",
        capabilities=[
            _cap("benchmark_analysis", "Design and analyze performance benchmarks"),
            _cap("experiment_design", "Structure benchmarks as repeatable experiments"),
            _cap("evaluation", "Evaluate system capabilities against benchmarks"),
            _cap("performance_metrics", "Define metrics and scoring rubrics"),
        ],
    ),
    AgentProfile(
        id="evaluation_agent", name="Evaluation Agent",
        role="Evaluation", tier=2, connector_type="internal",
        description="Evaluates experiment results and strategy outcomes",
        capabilities=[
            _cap("evaluation", "Evaluate outcomes against success criteria"),
            _cap("hypothesis_testing", "Test whether results confirm hypotheses"),
            _cap("statistical_analysis", "Apply statistical tests to results"),
            _cap("benchmark_analysis", "Compare results to historical benchmarks"),
            _cap("reflection", "Reflect on evaluation methodology improvements"),
        ],
    ),
    AgentProfile(
        id="backtester", name="Backtesting Agent",
        role="Backtesting", tier=2, connector_type="internal",
        description="Backtests strategies against historical data before deployment",
        capabilities=[
            _cap("backtesting", "Run strategies against historical data"),
            _cap("evaluation", "Evaluate backtest results for viability"),
            _cap("statistical_analysis", "Analyze statistical significance of results"),
            _cap("benchmark_analysis", "Compare strategy returns to benchmarks"),
        ],
    ),
    AgentProfile(
        id="simulator_agent", name="Simulation Agent",
        role="Simulation", tier=2, connector_type="internal",
        description="Runs simulations to validate strategies before live execution",
        capabilities=[
            _cap("scenario_simulation", "Run multi-scenario simulations"),
            _cap("experiment_design", "Design simulation parameters and controls"),
            _cap("evaluation", "Evaluate simulation outcomes and edge cases"),
            _cap("backtesting", "Simulate strategies against historical conditions"),
            _cap("risk_assessment", "Assess risk profiles through Monte Carlo methods"),
        ],
    ),
    AgentProfile(
        id="optimization_researcher", name="Optimization Researcher",
        role="Optimization Research", tier=2, connector_type="internal",
        description="Researches optimization techniques for system improvement",
        capabilities=[
            _cap("optimization", "Research and apply optimization algorithms"),
            _cap("benchmark_analysis", "Benchmark optimization approaches"),
            _cap("experiment_design", "Design experiments to test optimizations"),
            _cap("knowledge_expansion", "Discover new optimization techniques"),
            _cap("evaluation", "Evaluate optimization impact on system performance"),
        ],
    ),
    AgentProfile(
        id="experiment_validator", name="Experiment Validation Agent",
        role="Validation", tier=2, connector_type="internal",
        description="Validates experiment results for statistical significance",
        capabilities=[
            _cap("hypothesis_testing", "Validate hypotheses with statistical rigor"),
            _cap("evaluation", "Evaluate experiment validity and reliability"),
            _cap("statistical_analysis", "Run significance tests on experiment data"),
            _cap("benchmark_analysis", "Compare results to expected baselines"),
        ],
    ),
    AgentProfile(
        id="feedback_collector", name="Feedback Collector",
        role="Feedback Collection", tier=2, connector_type="internal",
        description="Collects, categorizes, and routes user and system feedback for continuous improvement",
        capabilities=[
            _cap("data_collection", "Collect feedback from user interactions and system events"),
            _cap("pattern_recognition", "Categorize feedback into themes and priority buckets"),
            _cap("data_analysis", "Analyze feedback sentiment and urgency"),
            _cap("knowledge_expansion", "Convert feedback insights into learning objectives"),
            _cap("summarization", "Produce feedback digests for review cycles"),
        ],
        metadata={"priority": 2},
    ),
    AgentProfile(
        id="ab_test_analyzer", name="A/B Test Analyzer",
        role="A/B Testing", tier=2, connector_type="internal",
        description="Designs and analyzes A/B tests to make data-driven improvement decisions",
        capabilities=[
            _cap("experiment_design", "Design statistically valid A/B and multivariate tests"),
            _cap("statistical_analysis", "Calculate significance, power, and confidence intervals"),
            _cap("hypothesis_testing", "Determine winner variants from test results"),
            _cap("evaluation", "Evaluate secondary and guardrail metrics alongside primary"),
            _cap("benchmark_analysis", "Compare A/B results against historical baselines"),
        ],
        metadata={"priority": 2},
    ),
    AgentProfile(
        id="curriculum_designer", name="Curriculum Designer",
        role="Curriculum Design", tier=2, connector_type="internal",
        description="Designs structured learning curricula for agents and system capability expansion",
        capabilities=[
            _cap("learning_strategy", "Design progressive learning sequences and skill ladders"),
            _cap("gap_analysis", "Identify knowledge gaps that curricula should address"),
            _cap("skill_creation", "Create skill modules aligned with curriculum objectives"),
            _cap("evaluation", "Evaluate curriculum effectiveness and completion rates"),
            _cap("knowledge_expansion", "Research best curriculum design frameworks and methods"),
        ],
        metadata={"priority": 2},
    ),
    AgentProfile(
        id="benchmark_runner", name="Benchmark Runner",
        role="Benchmark Execution", tier=2, connector_type="internal",
        description="Executes benchmark suites on schedule and tracks performance over time",
        capabilities=[
            _cap("benchmark_analysis", "Run standard and custom benchmarks against system components"),
            _cap("automation", "Schedule and automate benchmark execution pipelines"),
            _cap("monitoring", "Track benchmark score trends and regressions over time"),
            _cap("performance_metrics", "Collect and store performance metric time series"),
            _cap("summarization", "Produce benchmark run reports with trend analysis"),
        ],
        metadata={"priority": 2},
    ),
    AgentProfile(
        id="regression_detector", name="Regression Detector",
        role="Regression Detection", tier=2, connector_type="internal",
        description="Detects performance and quality regressions in code, models, and system metrics",
        capabilities=[
            _cap("benchmark_analysis", "Compare current and baseline benchmark scores"),
            _cap("anomaly_detection", "Flag statistically significant regressions"),
            _cap("monitoring", "Continuously monitor key metrics for degradation"),
            _cap("evaluation", "Triage regressions by severity and business impact"),
            _cap("debugging", "Investigate root causes of detected regressions"),
        ],
        metadata={"priority": 1},
    ),
]
