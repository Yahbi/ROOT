"""Calculator, code analysis, financial, and decision tool plugin builders."""

from __future__ import annotations

import ast
import logging
import operator
from pathlib import Path

from backend.core.plugin_engine import Plugin, PluginTool

logger = logging.getLogger("root.plugins")


def register_utility_plugins(engine, memory_engine=None, skill_engine=None) -> None:
    """Register calculator, code analysis, financial, and decision plugins."""
    _register_calculator(engine)
    _register_code_analysis(engine)
    _register_financial(engine)
    _register_decisions(engine)


# ── Calculator Plugin ───────────────────────────────────────────

_SAFE_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.USub: operator.neg,
}


def _safe_eval(node):
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("Only numbers allowed")
    if isinstance(node, ast.BinOp):
        op = _SAFE_OPS.get(type(node.op))
        if not op:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op(_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp):
        op = _SAFE_OPS.get(type(node.op))
        if not op:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op(_safe_eval(node.operand))
    raise ValueError(f"Unsupported expression: {type(node).__name__}")


def _register_calculator(engine) -> None:
    def calculate(args):
        expr = args.get("expression", "")
        if not expr:
            return {"error": "expression is required"}
        try:
            tree = ast.parse(expr, mode="eval")
            result = _safe_eval(tree)
            return {"expression": expr, "result": result}
        except Exception as e:
            return {"expression": expr, "error": str(e)}

    engine.register(Plugin(
        id="calculator",
        name="Calculator",
        description="Safe mathematical expression evaluator",
        version="1.0.0",
        category="utility",
        tags=["math", "calculator"],
        tools=[
            PluginTool(
                name="calculate",
                description="Evaluate a mathematical expression safely (e.g., '2 * 3 + 4')",
                handler=calculate,
                parameters={
                    "type": "object",
                    "properties": {"expression": {"type": "string", "description": "Math expression"}},
                    "required": ["expression"],
                },
            ),
        ],
    ))


# ── Code Analysis Plugin ───────────────────────────────────────


def _register_code_analysis(engine) -> None:
    def analyze_python(args):
        path = args.get("path", "")
        if not path:
            return {"error": "path is required"}
        try:
            source = Path(path).read_text(errors="replace")
            tree = ast.parse(source)
            classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
            functions = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
            imports = []
            for n in ast.walk(tree):
                if isinstance(n, ast.Import):
                    imports.extend(a.name for a in n.names)
                elif isinstance(n, ast.ImportFrom):
                    if n.module:
                        imports.append(n.module)
            return {
                "path": path,
                "lines": len(source.splitlines()),
                "classes": classes,
                "functions": functions[:30],
                "imports": sorted(set(imports)),
            }
        except Exception as e:
            return {"path": path, "error": str(e)}

    engine.register(Plugin(
        id="code_analysis",
        name="Code Analyzer",
        description="Analyze Python files — extract classes, functions, imports",
        version="1.0.0",
        category="development",
        tags=["code", "python", "analysis"],
        tools=[
            PluginTool(
                name="analyze_python",
                description="Analyze a Python file: list classes, functions, imports, line count",
                handler=analyze_python,
                parameters={
                    "type": "object",
                    "properties": {"path": {"type": "string", "description": "Path to Python file"}},
                    "required": ["path"],
                },
            ),
        ],
    ))


# ── Financial Intelligence Plugin ──────────────────────────────


def _register_financial(engine) -> None:
    def compound_interest(args):
        """Calculate compound interest growth."""
        principal = float(args.get("principal", 0))
        rate = float(args.get("annual_rate", 0.07))
        years = int(args.get("years", 10))
        monthly_add = float(args.get("monthly_addition", 0))

        if principal <= 0 and monthly_add <= 0:
            return {"error": "Need principal or monthly_addition > 0"}

        monthly_rate = rate / 12
        months = years * 12
        balance = principal
        timeline = []

        for year in range(1, years + 1):
            for _ in range(12):
                balance = balance * (1 + monthly_rate) + monthly_add
            timeline.append({"year": year, "balance": round(balance, 2)})

        total_invested = principal + (monthly_add * months)
        return {
            "final_balance": round(balance, 2),
            "total_invested": round(total_invested, 2),
            "total_interest": round(balance - total_invested, 2),
            "roi_pct": round((balance / total_invested - 1) * 100, 1) if total_invested > 0 else 0,
            "timeline": timeline,
        }

    def revenue_projector(args):
        """Project SaaS revenue growth."""
        current_mrr = float(args.get("current_mrr", 0))
        monthly_growth_pct = float(args.get("monthly_growth_pct", 10))
        months = int(args.get("months", 12))
        churn_pct = float(args.get("monthly_churn_pct", 3))
        price_per_customer = float(args.get("price_per_customer", 99))

        net_growth = (monthly_growth_pct - churn_pct) / 100
        projections = []
        mrr = current_mrr

        for month in range(1, months + 1):
            mrr = mrr * (1 + net_growth)
            customers = round(mrr / price_per_customer) if price_per_customer > 0 else 0
            projections.append({
                "month": month,
                "mrr": round(mrr, 2),
                "arr": round(mrr * 12, 2),
                "customers": customers,
            })

        return {
            "starting_mrr": current_mrr,
            "ending_mrr": round(mrr, 2),
            "ending_arr": round(mrr * 12, 2),
            "net_monthly_growth": f"{net_growth * 100:.1f}%",
            "projections": projections,
        }

    def roi_calculator(args):
        """Calculate return on investment."""
        investment = float(args.get("investment", 0))
        monthly_return = float(args.get("monthly_return", 0))
        time_hours = float(args.get("time_hours", 0))
        hourly_rate = float(args.get("hourly_rate", 100))

        if investment <= 0 and time_hours <= 0:
            return {"error": "Need investment or time_hours > 0"}

        total_cost = investment + (time_hours * hourly_rate)
        annual_return = monthly_return * 12
        payback_months = round(total_cost / monthly_return, 1) if monthly_return > 0 else float("inf")
        roi_1yr = round((annual_return / total_cost - 1) * 100, 1) if total_cost > 0 else 0

        return {
            "total_cost": round(total_cost, 2),
            "monthly_return": monthly_return,
            "annual_return": round(annual_return, 2),
            "payback_months": payback_months,
            "roi_1yr_pct": roi_1yr,
            "verdict": "GOOD" if payback_months < 6 else "OK" if payback_months < 12 else "RISKY",
        }

    engine.register(Plugin(
        id="financial",
        name="Financial Intelligence",
        description="Compound interest, revenue projections, ROI analysis",
        version="1.0.0",
        category="financial",
        tags=["finance", "money", "revenue", "roi", "investment"],
        tools=[
            PluginTool(
                name="compound_interest",
                description="Calculate compound interest growth over time with optional monthly additions",
                handler=compound_interest,
                parameters={
                    "type": "object",
                    "properties": {
                        "principal": {"type": "number", "description": "Starting amount"},
                        "annual_rate": {"type": "number", "description": "Annual interest rate (0.07 = 7%)", "default": 0.07},
                        "years": {"type": "integer", "description": "Number of years", "default": 10},
                        "monthly_addition": {"type": "number", "description": "Monthly contribution", "default": 0},
                    },
                },
            ),
            PluginTool(
                name="revenue_projector",
                description="Project SaaS revenue: MRR growth, churn, ARR, customer count",
                handler=revenue_projector,
                parameters={
                    "type": "object",
                    "properties": {
                        "current_mrr": {"type": "number", "description": "Current monthly recurring revenue"},
                        "monthly_growth_pct": {"type": "number", "description": "Monthly growth %", "default": 10},
                        "months": {"type": "integer", "description": "Months to project", "default": 12},
                        "monthly_churn_pct": {"type": "number", "description": "Monthly churn %", "default": 3},
                        "price_per_customer": {"type": "number", "description": "Price per customer/mo", "default": 99},
                    },
                },
            ),
            PluginTool(
                name="roi_calculator",
                description="Calculate ROI: investment + time cost → payback period and annual return",
                handler=roi_calculator,
                parameters={
                    "type": "object",
                    "properties": {
                        "investment": {"type": "number", "description": "Money invested ($)"},
                        "monthly_return": {"type": "number", "description": "Expected monthly return ($)"},
                        "time_hours": {"type": "number", "description": "Time invested (hours)", "default": 0},
                        "hourly_rate": {"type": "number", "description": "Your hourly rate ($)", "default": 100},
                    },
                },
            ),
        ],
    ))


# ── Decision Analysis Plugin ───────────────────────────────────


def _register_decisions(engine) -> None:
    def pros_cons_matrix(args):
        """Structured pros/cons analysis with weighted scoring."""
        subject = args.get("subject", "Decision")
        pros = args.get("pros", [])
        cons = args.get("cons", [])

        if not pros and not cons:
            return {"error": "Provide at least some pros or cons"}

        pro_score = sum(p.get("weight", 1) for p in pros) if isinstance(pros[0] if pros else "", dict) else len(pros)
        con_score = sum(c.get("weight", 1) for c in cons) if isinstance(cons[0] if cons else "", dict) else len(cons)
        net = pro_score - con_score

        return {
            "subject": subject,
            "pro_count": len(pros),
            "con_count": len(cons),
            "pro_score": pro_score,
            "con_score": con_score,
            "net_score": net,
            "verdict": "PROCEED" if net > 2 else "CONSIDER" if net > 0 else "AVOID",
        }

    def opportunity_scorer(args):
        """Score a business opportunity on multiple dimensions."""
        revenue_potential = float(args.get("revenue_potential", 0))  # 0-10
        time_to_revenue = float(args.get("time_to_revenue", 5))  # 0-10 (10=fast)
        scalability = float(args.get("scalability", 5))  # 0-10
        defensibility = float(args.get("defensibility", 5))  # 0-10
        skill_fit = float(args.get("skill_fit", 5))  # 0-10
        capital_needed = float(args.get("capital_needed", 5))  # 0-10 (10=none needed)

        weights = {
            "revenue_potential": 0.25,
            "time_to_revenue": 0.20,
            "scalability": 0.15,
            "defensibility": 0.15,
            "skill_fit": 0.15,
            "capital_needed": 0.10,
        }

        scores = {
            "revenue_potential": revenue_potential,
            "time_to_revenue": time_to_revenue,
            "scalability": scalability,
            "defensibility": defensibility,
            "skill_fit": skill_fit,
            "capital_needed": capital_needed,
        }

        weighted = sum(scores[k] * weights[k] for k in weights)

        return {
            "scores": scores,
            "weights": weights,
            "weighted_total": round(weighted, 2),
            "max_possible": 10.0,
            "grade": "A" if weighted >= 8 else "B" if weighted >= 6.5 else "C" if weighted >= 5 else "D" if weighted >= 3 else "F",
            "verdict": "STRONG BUY" if weighted >= 8 else "BUY" if weighted >= 6.5 else "HOLD" if weighted >= 5 else "PASS",
        }

    engine.register(Plugin(
        id="decisions",
        name="Decision Analysis",
        description="Structured decision-making: pros/cons matrix, opportunity scoring",
        version="1.0.0",
        category="analysis",
        tags=["decisions", "analysis", "scoring", "evaluation"],
        tools=[
            PluginTool(
                name="pros_cons_matrix",
                description="Weighted pros/cons analysis for any decision",
                handler=pros_cons_matrix,
                parameters={
                    "type": "object",
                    "properties": {
                        "subject": {"type": "string", "description": "What you're deciding"},
                        "pros": {"type": "array", "items": {"type": "string"}, "description": "List of pros"},
                        "cons": {"type": "array", "items": {"type": "string"}, "description": "List of cons"},
                    },
                    "required": ["subject"],
                },
            ),
            PluginTool(
                name="opportunity_scorer",
                description="Score a business opportunity across 6 dimensions (0-10 each): revenue, speed, scale, defense, fit, capital",
                handler=opportunity_scorer,
                parameters={
                    "type": "object",
                    "properties": {
                        "revenue_potential": {"type": "number", "description": "Revenue potential (0-10)"},
                        "time_to_revenue": {"type": "number", "description": "Speed to revenue (0-10, 10=fast)"},
                        "scalability": {"type": "number", "description": "Scalability (0-10)"},
                        "defensibility": {"type": "number", "description": "Competitive moat (0-10)"},
                        "skill_fit": {"type": "number", "description": "Fit with Yohan's skills (0-10)"},
                        "capital_needed": {"type": "number", "description": "Capital efficiency (0-10, 10=none needed)"},
                    },
                },
            ),
        ],
    ))
