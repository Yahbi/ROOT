"""
Knowledge Generator — programmatically generates thousands of knowledge entries
by combining domain templates with specific data points.

Generates entries for: trading indicators, stock analysis, economic data,
programming patterns, mathematical formulas, and more.

Run: python -m backend.tools.generate_knowledge
"""

import json
import os
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "knowledge" / "generated"


def generate_trading_indicators():
    """Generate entries for every common trading indicator with multiple timeframes."""
    indicators = [
        ("RSI", "Relative Strength Index", "100 - 100/(1+RS)", "14", ">70 overbought, <30 oversold"),
        ("MACD", "Moving Average Convergence Divergence", "12EMA - 26EMA", "12,26,9", "signal crossover"),
        ("Bollinger Bands", "Bollinger Bands", "SMA(20) ± 2σ", "20,2", "squeeze = low volatility"),
        ("Stochastic", "Stochastic Oscillator", "%K = (C-L14)/(H14-L14)*100", "14,3,3", ">80 overbought, <20 oversold"),
        ("CCI", "Commodity Channel Index", "(TP-SMA(TP))/(0.015*MD)", "20", ">100 bullish, <-100 bearish"),
        ("Williams %R", "Williams Percent Range", "(HH-C)/(HH-LL)*-100", "14", ">-20 overbought, <-80 oversold"),
        ("MFI", "Money Flow Index", "100 - 100/(1+MFR)", "14", ">80 overbought, <20 oversold"),
        ("ADX", "Average Directional Index", "smoothed(|+DI - -DI|/(+DI + -DI))*100", "14", ">25 trending, <20 ranging"),
        ("ATR", "Average True Range", "SMA(max(H-L, |H-Cp|, |L-Cp|), 14)", "14", "volatility measure, stop placement"),
        ("OBV", "On-Balance Volume", "cumulative(vol if C>Cp else -vol)", "n/a", "divergence = reversal signal"),
        ("VWAP", "Volume Weighted Average Price", "Σ(P×V)/ΣV", "session", "institutional benchmark"),
        ("Ichimoku", "Ichimoku Cloud", "Tenkan(9)+Kijun(26)+Senkou A/B+Chikou", "9,26,52", "cloud = support/resistance"),
        ("Parabolic SAR", "Parabolic Stop and Reverse", "SAR(n+1) = SAR(n) + AF*(EP-SAR(n))", "0.02,0.2", "trend following stops"),
        ("Keltner", "Keltner Channel", "EMA(20) ± 2*ATR(10)", "20,10,2", "narrower than Bollinger"),
        ("Donchian", "Donchian Channel", "highest high(20) / lowest low(20)", "20", "turtle trading breakout"),
        ("ROC", "Rate of Change", "(C - C_n)/C_n * 100", "12", "momentum oscillator"),
        ("TRIX", "Triple Exponential Average", "1-period ROC of triple-smoothed EMA", "15", "filter noise, signal crossover"),
        ("Elder Ray", "Elder Ray Index", "Bull Power=H-EMA(13), Bear Power=L-EMA(13)", "13", "trend strength"),
        ("Chaikin MF", "Chaikin Money Flow", "Σ(((C-L)-(H-C))/(H-L)*V)/Σ(V)", "20", ">0.1 buying, <-0.1 selling"),
        ("Aroon", "Aroon Indicator", "Aroon Up = ((n - periods since n-high)/n)*100", "25", ">70 strong trend"),
    ]

    timeframes = ["1min", "5min", "15min", "1hour", "4hour", "daily", "weekly"]
    entries = []

    for name, full_name, formula, params, interpretation in indicators:
        # Base entry
        entries.append({
            "content": f"{full_name} ({name}) is calculated as {formula} with default period {params}. Standard interpretation: {interpretation}. Best used with confirming indicators to reduce false signals.",
            "type": "fact", "tags": [name.lower().replace(" ", "_"), "technical_analysis", "indicator"],
            "source": "trading_knowledge"
        })
        # Timeframe entries
        for tf in ["daily", "weekly", "1hour"]:
            entries.append({
                "content": f"{name} on {tf} timeframe: use period {params} for standard signals. On {tf} charts, {name} is most reliable when combined with volume confirmation and trend direction from higher timeframe.",
                "type": "skill", "tags": [name.lower().replace(" ", "_"), tf, "technical_analysis"],
                "source": "trading_knowledge"
            })
        # Divergence entry
        entries.append({
            "content": f"{name} divergence: when price makes new high but {name} makes lower high (bearish divergence) or price makes new low but {name} makes higher low (bullish divergence). Divergence signals are strongest on daily/weekly timeframes and often precede trend reversals by 2-5 bars.",
            "type": "learning", "tags": [name.lower().replace(" ", "_"), "divergence", "reversal"],
            "source": "trading_knowledge"
        })

    return entries


def generate_stock_analysis():
    """Generate entries for major stocks and sectors."""
    stocks = [
        ("AAPL", "Apple", "Technology", 3000, "iPhone, Services, Mac, iPad, Wearables"),
        ("MSFT", "Microsoft", "Technology", 3100, "Azure, Office 365, Windows, Gaming, LinkedIn"),
        ("GOOGL", "Alphabet", "Technology", 2000, "Search, YouTube, Cloud, Android, Waymo"),
        ("AMZN", "Amazon", "Consumer Discretionary", 1900, "AWS, E-commerce, Prime, Advertising"),
        ("NVDA", "NVIDIA", "Technology", 3200, "GPUs, Data Center, AI/ML, Gaming, Automotive"),
        ("META", "Meta Platforms", "Technology", 1400, "Facebook, Instagram, WhatsApp, Metaverse, AI"),
        ("TSLA", "Tesla", "Consumer Discretionary", 800, "EVs, Energy Storage, Solar, Autonomy, Robotaxi"),
        ("BRK.B", "Berkshire Hathaway", "Financials", 900, "Insurance, BNSF, Energy, Manufacturing, Investments"),
        ("JPM", "JPMorgan Chase", "Financials", 600, "Investment Banking, Consumer Banking, Asset Management"),
        ("V", "Visa", "Financials", 550, "Payment Processing, Cross-border, Digital Payments"),
        ("JNJ", "Johnson & Johnson", "Healthcare", 400, "Pharmaceuticals, MedTech, Consumer Health"),
        ("UNH", "UnitedHealth Group", "Healthcare", 550, "Insurance, Optum, Pharmacy, Data Analytics"),
        ("XOM", "Exxon Mobil", "Energy", 500, "Oil Production, Refining, Chemicals, LNG"),
        ("PG", "Procter & Gamble", "Consumer Staples", 370, "Beauty, Grooming, Healthcare, Fabric, Home Care"),
        ("HD", "Home Depot", "Consumer Discretionary", 380, "Home Improvement Retail, Pro Customers"),
        ("MA", "Mastercard", "Financials", 430, "Payment Technology, Cross-border, Data Services"),
        ("COST", "Costco", "Consumer Staples", 380, "Warehouse Retail, Membership Model, Kirkland"),
        ("ABBV", "AbbVie", "Healthcare", 320, "Immunology (Humira/Skyrizi), Oncology, Neuroscience"),
        ("CRM", "Salesforce", "Technology", 280, "CRM, Marketing Cloud, Slack, Data Cloud, AI"),
        ("LLY", "Eli Lilly", "Healthcare", 800, "GLP-1 (Mounjaro/Zepbound), Oncology, Neuroscience"),
    ]

    entries = []
    for ticker, name, sector, mcap_approx, segments in stocks:
        entries.append({
            "content": f"{name} ({ticker}) is a {sector} company with ~${mcap_approx}B market cap. Key segments: {segments}. As a mega-cap, it's a core holding in most index funds (SPY, QQQ) and influences sector-wide moves.",
            "type": "fact", "tags": [ticker.lower(), sector.lower().replace(" ", "_"), "stock_analysis"],
            "source": "trading_knowledge"
        })
        entries.append({
            "content": f"When analyzing {ticker}, focus on: revenue growth rate (YoY), operating margin trends, free cash flow yield (FCF/market cap), and forward P/E relative to 5-year average. For {sector} stocks, compare against sector ETF (XL{sector[0]}) performance.",
            "type": "skill", "tags": [ticker.lower(), "fundamental_analysis", "valuation"],
            "source": "trading_knowledge"
        })

    return entries


def generate_economic_indicators():
    """Generate entries for global economic indicators."""
    indicators = [
        ("GDP", "Gross Domestic Product", "quarterly", "C+I+G+(X-M)", ">2% growth healthy, <0% recession", "BEA"),
        ("CPI", "Consumer Price Index", "monthly", "weighted basket of goods", "2% Fed target, >3% hot inflation", "BLS"),
        ("PCE", "Personal Consumption Expenditures", "monthly", "broader than CPI", "Fed's preferred inflation gauge", "BEA"),
        ("NFP", "Non-Farm Payrolls", "monthly first Friday", "net new jobs", ">200K strong, <100K weak", "BLS"),
        ("Unemployment Rate", "U-3 Unemployment", "monthly", "unemployed/labor force", "<4% tight labor market", "BLS"),
        ("PMI", "Purchasing Managers Index", "monthly", "survey of purchasing managers", ">50 expansion, <50 contraction", "ISM"),
        ("PPI", "Producer Price Index", "monthly", "wholesale price changes", "leading indicator of CPI", "BLS"),
        ("Retail Sales", "Advance Retail Sales", "monthly", "total retail receipts", "70% of GDP is consumption", "Census Bureau"),
        ("Housing Starts", "New Residential Construction", "monthly", "new home construction began", "sensitive to interest rates", "Census Bureau"),
        ("Consumer Confidence", "Conference Board Consumer Confidence", "monthly", "survey of household expectations", ">100 optimistic, <100 pessimistic", "Conference Board"),
        ("Initial Claims", "Initial Jobless Claims", "weekly Thursday", "new unemployment filings", "<200K very strong, >300K concerning", "DOL"),
        ("Industrial Production", "Industrial Production Index", "monthly", "output of factories/mines/utilities", "manufacturing health gauge", "Fed"),
        ("Trade Balance", "International Trade in Goods and Services", "monthly", "exports minus imports", "deficit = importing more than exporting", "Census/BEA"),
        ("Fed Funds Rate", "Federal Funds Target Rate", "8 FOMC meetings/year", "overnight interbank lending rate", "primary monetary policy tool", "Federal Reserve"),
        ("10Y Treasury Yield", "10-Year Treasury Note Yield", "continuous", "government bond yield", "benchmark for mortgages, risk-free rate proxy", "Treasury"),
        ("2s10s Spread", "2-Year minus 10-Year Treasury Spread", "continuous", "yield curve slope", "inverted = recession signal (12-18mo lead)", "Treasury"),
        ("VIX", "CBOE Volatility Index", "continuous", "implied vol of SPX options", "<15 complacent, 15-25 normal, >25 fearful, >35 panic", "CBOE"),
        ("Dollar Index", "DXY US Dollar Index", "continuous", "USD vs 6 major currencies", "strong dollar = headwind for multinationals", "ICE"),
        ("Copper Price", "Copper Futures", "continuous", "industrial metal", "'Dr. Copper' — leading economic indicator", "COMEX"),
        ("Oil Price", "WTI Crude Oil", "continuous", "benchmark US oil", ">$80 inflationary, <$50 deflationary signal", "NYMEX"),
    ]

    entries = []
    for name, full_name, frequency, calculation, interpretation, source_agency in indicators:
        entries.append({
            "content": f"{full_name} ({name}) is released {frequency} by {source_agency}. Calculation: {calculation}. Market interpretation: {interpretation}. Traders watch for surprises vs consensus estimates — the deviation from expectations moves markets more than the absolute number.",
            "type": "fact", "tags": [name.lower().replace(" ", "_").replace("-", ""), "economic_indicator", "macro"],
            "source": "economics_knowledge"
        })
        entries.append({
            "content": f"Trading around {name} release: position before announcement carries event risk. The market typically prices in consensus expectations — a beat drives rally, miss drives selloff. Volatility spikes around release and settles within 30-60 minutes. Use options straddles for pure volatility play.",
            "type": "skill", "tags": [name.lower().replace(" ", "_").replace("-", ""), "event_trading", "macro"],
            "source": "trading_knowledge"
        })

    return entries


def generate_programming_patterns():
    """Generate entries for design patterns and coding concepts."""
    patterns = [
        ("Singleton", "creational", "Ensure a class has only one instance with global access point. Use module-level instance in Python. Thread-safe with threading.Lock or metaclass approach."),
        ("Factory Method", "creational", "Define interface for creating objects, let subclasses decide. In Python: classmethod alternative constructors like datetime.fromtimestamp()."),
        ("Abstract Factory", "creational", "Create families of related objects without specifying concrete classes. Example: UI toolkit creating buttons+menus for Windows vs Mac."),
        ("Builder", "creational", "Construct complex objects step by step. Separate construction from representation. Python: method chaining with self-returning methods."),
        ("Prototype", "creational", "Create new objects by copying existing ones. Python: copy.deepcopy() or __copy__/__deepcopy__ methods. Useful when object creation is expensive."),
        ("Adapter", "structural", "Convert interface of a class to another interface clients expect. Wrapper pattern. Python: composition over inheritance for adapting APIs."),
        ("Decorator", "structural", "Add responsibilities dynamically without modifying original. Python @decorator syntax wraps functions. functools.wraps preserves metadata."),
        ("Facade", "structural", "Simplified interface to complex subsystem. Example: requests library facades urllib, http.client, ssl. Reduces coupling to subsystem internals."),
        ("Proxy", "structural", "Provide surrogate for another object. Types: virtual (lazy init), protection (access control), remote (RPC), caching proxy. Python: __getattr__ delegation."),
        ("Composite", "structural", "Tree structure where leaf and composite nodes share interface. Example: file system (files and directories both have size/name). Recursive operations."),
        ("Observer", "behavioral", "One-to-many dependency: when subject changes, all observers notified. Python: callbacks, signals, event emitters, pub/sub. Decouples sender from receivers."),
        ("Strategy", "behavioral", "Define family of algorithms, encapsulate each, make interchangeable. Python: pass functions as arguments (first-class functions). Eliminates conditional logic."),
        ("Command", "behavioral", "Encapsulate request as object. Supports undo/redo, queuing, logging. Python: callable objects with __call__. Example: GUI button actions."),
        ("Template Method", "behavioral", "Define algorithm skeleton, let subclasses override specific steps. Python: abstract base classes with abc.ABC. Hook methods for optional customization."),
        ("Iterator", "behavioral", "Sequential access to elements without exposing underlying structure. Python: __iter__/__next__ protocol, generators with yield. Lazy evaluation saves memory."),
        ("State", "behavioral", "Object behavior changes based on internal state. Each state is a class with its own behavior. Eliminates large if/elif chains. Finite state machines."),
        ("Chain of Responsibility", "behavioral", "Pass request along chain of handlers. Each handler decides to process or pass. Example: middleware pipelines, exception handling, logging chains."),
        ("Mediator", "behavioral", "Centralize complex communications between objects. Reduces many-to-many to one-to-many via mediator. Example: chat room, event bus, air traffic control."),
        ("Repository", "structural", "Abstract data storage behind collection-like interface. Methods: get(id), find(criteria), add(entity), remove(entity). Decouples domain from persistence."),
        ("Unit of Work", "behavioral", "Track changes to objects during business transaction, then commit/rollback atomically. Coordinates writes to avoid partial updates. SQLAlchemy Session pattern."),
        ("CQRS", "architectural", "Separate read (Query) and write (Command) models. Read model denormalized for fast queries. Write model normalized for consistency. Event sourcing complement."),
        ("Event Sourcing", "architectural", "Store state changes as immutable event log instead of current state. Replay events to reconstruct state. Full audit trail, temporal queries, event-driven."),
        ("Circuit Breaker", "behavioral", "Prevent cascade failures. States: CLOSED (normal), OPEN (failing, fast-fail), HALF-OPEN (testing recovery). Threshold: 5 failures. Recovery: 30-60s timeout."),
        ("Saga", "architectural", "Manage distributed transactions via sequence of local transactions with compensating actions. Choreography (events) vs orchestration (coordinator). No distributed locks."),
        ("Strangler Fig", "architectural", "Incrementally replace legacy system by routing requests to new system piece by piece. Zero downtime migration. Facade routes old→new based on feature flags."),
    ]

    entries = []
    for name, category, description in patterns:
        entries.append({
            "content": f"{name} ({category} pattern): {description}",
            "type": "fact", "tags": [name.lower().replace(" ", "_"), "design_pattern", category],
            "source": "engineering_knowledge"
        })

    return entries


def generate_math_formulas():
    """Generate entries for important mathematical formulas."""
    formulas = [
        ("Compound Interest", "A = P(1 + r/n)^(nt)", "P=principal, r=annual rate, n=compounds per year, t=years. Rule of 72: years to double ≈ 72/rate.", "finance"),
        ("Present Value", "PV = FV / (1 + r)^n", "Time value of money. $1 today is worth more than $1 tomorrow. Discount rate r reflects risk and opportunity cost.", "finance"),
        ("Black-Scholes Call", "C = S·N(d1) - K·e^(-rT)·N(d2)", "d1 = [ln(S/K) + (r + σ²/2)T] / (σ√T), d2 = d1 - σ√T. European call option pricing.", "finance"),
        ("Sharpe Ratio", "SR = (Rp - Rf) / σp", "Risk-adjusted return. Annualize daily: multiply by √252. Good >1.0, Very good >2.0, Excellent >3.0.", "finance"),
        ("Kelly Criterion", "f* = (bp - q) / b", "b=odds, p=win probability, q=1-p. Optimal bet fraction. Use half-Kelly (f*/2) in practice for safety.", "finance"),
        ("Value at Risk", "VaR(95%) = μ - 1.645σ", "95th percentile loss. Parametric assumes normal. Historical uses actual distribution. Monte Carlo simulates paths.", "finance"),
        ("Bayes Theorem", "P(A|B) = P(B|A)·P(A) / P(B)", "Updates probability given new evidence. Prior × Likelihood / Evidence = Posterior. Foundation of Bayesian inference.", "statistics"),
        ("Normal Distribution", "f(x) = (1/σ√2π)·e^(-(x-μ)²/2σ²)", "68% within 1σ, 95% within 2σ, 99.7% within 3σ. Central limit theorem: sum of many → Normal.", "statistics"),
        ("Linear Regression", "y = β₀ + β₁x + ε", "β₁ = Σ(xi-x̄)(yi-ȳ) / Σ(xi-x̄)². R² = 1 - SS_res/SS_tot. Assumptions: linearity, independence, normality, equal variance.", "statistics"),
        ("Shannon Entropy", "H(X) = -Σ p(x)·log₂(p(x))", "Measures information content / uncertainty. Max entropy = uniform distribution. Used in decision trees, compression, coding.", "information_theory"),
        ("Euclidean Distance", "d = √(Σ(xi - yi)²)", "L2 norm. Most common distance metric. Sensitive to scale — normalize features first. Alternative: Manhattan distance (L1).", "math"),
        ("Cosine Similarity", "cos(θ) = (A·B) / (||A||·||B||)", "Measures angle between vectors. Range [-1, 1]. Preferred for text embeddings. Invariant to magnitude, only measures direction.", "math"),
        ("Matrix Multiplication", "C_ij = Σ_k A_ik · B_kj", "A(m×n) × B(n×p) = C(m×p). O(n³) naive, O(n^2.37) Strassen. GPU-accelerated for neural networks. Batch = parallel matmuls.", "math"),
        ("Gradient Descent", "θ = θ - α·∇L(θ)", "α = learning rate. Variants: SGD (single sample), mini-batch (32-256), Adam (adaptive moment estimation). Learning rate schedule: cosine annealing.", "optimization"),
        ("Softmax", "σ(zi) = e^zi / Σ_j e^zj", "Converts logits to probabilities summing to 1. Temperature T: σ(zi/T) — high T = uniform, low T = peaked. Used in classification and attention.", "math"),
        ("Cross-Entropy Loss", "L = -Σ y·log(ŷ)", "Binary: L = -[y·log(ŷ) + (1-y)·log(1-ŷ)]. Standard loss for classification. Measures divergence between predicted and true distributions.", "math"),
        ("Fibonacci Sequence", "F(n) = F(n-1) + F(n-2)", "0,1,1,2,3,5,8,13,21,34,55,89... Golden ratio φ = (1+√5)/2 ≈ 1.618. Retracements: 23.6%, 38.2%, 50%, 61.8%, 78.6%.", "math"),
        ("Euler's Formula", "e^(iπ) + 1 = 0", "Links five fundamental constants. General form: e^(ix) = cos(x) + i·sin(x). Foundation of signal processing, quantum mechanics.", "math"),
        ("Binomial Distribution", "P(X=k) = C(n,k)·p^k·(1-p)^(n-k)", "n trials, p probability, k successes. Mean=np, Var=np(1-p). Approximates Normal when np>5 and n(1-p)>5.", "statistics"),
        ("Poisson Distribution", "P(X=k) = λ^k·e^(-λ) / k!", "Events per time interval, rate λ. Mean=Var=λ. Memoryless. Models: customer arrivals, website hits, defects per unit.", "statistics"),
    ]

    entries = []
    for name, formula, description, domain in formulas:
        entries.append({
            "content": f"{name}: {formula}. {description}",
            "type": "fact", "tags": [name.lower().replace(" ", "_").replace("'", ""), "formula", domain],
            "source": "math_knowledge"
        })

    return entries


def main():
    """Generate all knowledge and write to JSON files."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    generators = {
        "gen_trading_indicators.json": generate_trading_indicators,
        "gen_stock_analysis.json": generate_stock_analysis,
        "gen_economic_indicators.json": generate_economic_indicators,
        "gen_programming_patterns.json": generate_programming_patterns,
        "gen_math_formulas.json": generate_math_formulas,
    }

    total = 0
    for filename, generator in generators.items():
        entries = generator()
        filepath = DATA_DIR / filename
        with open(filepath, "w") as f:
            json.dump(entries, f, indent=2)
        count = len(entries)
        total += count
        print(f"  {filename}: {count} entries")

    print(f"\nTotal generated: {total} entries in {len(generators)} files")
    print(f"Files written to: {DATA_DIR}")


if __name__ == "__main__":
    main()
