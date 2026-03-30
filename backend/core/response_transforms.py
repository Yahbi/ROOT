"""
Post-processing transforms for LLM responses.

Inspired by G0DM0D3's STM (Semantic Transformation Modules). Makes trading
responses more decisive and actionable by stripping hedging, preambles,
and boosting confidence language.
"""

from __future__ import annotations

import re


class ResponseTransforms:
    """Static transform methods for LLM response post-processing."""

    # ------------------------------------------------------------------
    # Hedging language patterns
    # ------------------------------------------------------------------
    _HEDGE_REMOVALS = [
        (re.compile(r"\bI think\s+", re.IGNORECASE), ""),
        (re.compile(r"\bI believe\s+", re.IGNORECASE), ""),
        (re.compile(r"\bIt seems\s+(that\s+)?", re.IGNORECASE), ""),
        (re.compile(r"\bIt appears\s+(that\s+)?", re.IGNORECASE), ""),
        (re.compile(r"\bperhaps\s+", re.IGNORECASE), ""),
        (re.compile(r"\bmaybe\s+", re.IGNORECASE), ""),
        (re.compile(r"\bmight\b", re.IGNORECASE), "will"),
        (re.compile(r"\bcould potentially\b", re.IGNORECASE), "will"),
        (re.compile(r"\bit's possible that\s+", re.IGNORECASE), ""),
        (re.compile(r"\bin my opinion,?\s*", re.IGNORECASE), ""),
    ]

    _HEDGE_REPLACEMENTS = [
        (re.compile(r"\bshould consider\b", re.IGNORECASE), "should"),
        (re.compile(r"\bmay want to\b", re.IGNORECASE), "should"),
        (re.compile(r"\bcould be\b", re.IGNORECASE), "is"),
    ]

    # ------------------------------------------------------------------
    # Preamble / filler patterns
    # ------------------------------------------------------------------
    _OPENING_FILLERS = re.compile(
        r"^("
        r"Sure,?\s*I'?d?\s*be\s+happy\s+to[.!]?\s*"
        r"|Great\s+question[.!]?\s*"
        r"|Let\s+me\s+help\s+you\s+with\s+that[.!]?\s*"
        r"|As\s+an?\s+AI[^.]*[.]\s*"
        r"|Based\s+on\s+my\s+analysis,?\s*"
        r"|Absolutely[.!]?\s*"
        r"|Of\s+course[.!]?\s*"
        r"|Certainly[.!]?\s*"
        r")+",
        re.IGNORECASE | re.MULTILINE,
    )

    _CLOSING_FILLERS = re.compile(
        r"("
        r"I\s+hope\s+this\s+helps[.!]?\s*"
        r"|Let\s+me\s+know\s+if\s+you[^.]*[.]?\s*"
        r"|Feel\s+free\s+to\s+ask[^.]*[.]?\s*"
        r"|Is\s+there\s+anything\s+else[^.]*[.]?\s*"
        r"|Happy\s+to\s+help[^.]*[.]?\s*"
        r")+\s*$",
        re.IGNORECASE | re.MULTILINE,
    )

    # ------------------------------------------------------------------
    # Confidence patterns
    # ------------------------------------------------------------------
    _CONFIDENCE_BOOSTS = [
        (re.compile(r"\brelatively strong\b", re.IGNORECASE), "strong"),
        (re.compile(r"\bsomewhat positive\b", re.IGNORECASE), "positive"),
        (re.compile(r"\bfairly likely\b", re.IGNORECASE), "likely"),
        (re.compile(r"\bsomewhat likely\b", re.IGNORECASE), "likely"),
        (re.compile(r"\brelatively high\b", re.IGNORECASE), "high"),
        (re.compile(r"\bsomewhat bearish\b", re.IGNORECASE), "bearish"),
        (re.compile(r"\bsomewhat bullish\b", re.IGNORECASE), "bullish"),
        (re.compile(r"\bslightly positive\b", re.IGNORECASE), "positive"),
        (re.compile(r"\bslightly negative\b", re.IGNORECASE), "negative"),
        (re.compile(r"\bmodestly higher\b", re.IGNORECASE), "higher"),
    ]

    # ------------------------------------------------------------------
    # Trading action extraction
    # ------------------------------------------------------------------
    _TRADING_ACTION = re.compile(
        r"\b(BUY|SELL|HOLD|LONG|SHORT)\s+"
        r"([A-Z]{1,5})"
        r"(?:\s+(?:@|at)\s*\$?([\d,.]+))?",
        re.IGNORECASE,
    )

    # ------------------------------------------------------------------
    # Public transform methods
    # ------------------------------------------------------------------

    @staticmethod
    def hedge_reduce(text: str) -> str:
        """Remove hedging language to make responses more decisive."""
        for pattern, replacement in ResponseTransforms._HEDGE_REMOVALS:
            text = pattern.sub(replacement, text)
        for pattern, replacement in ResponseTransforms._HEDGE_REPLACEMENTS:
            text = pattern.sub(replacement, text)
        # Clean up double spaces left by removals
        text = re.sub(r"  +", " ", text)
        # Fix capitalization after removal at sentence start
        text = re.sub(r"(?<=\.\s)([a-z])", lambda m: m.group(1).upper(), text)
        text = re.sub(r"^([a-z])", lambda m: m.group(1).upper(), text)
        return text.strip()

    @staticmethod
    def direct_mode(text: str) -> str:
        """Strip preambles and closing filler for direct responses."""
        text = ResponseTransforms._OPENING_FILLERS.sub("", text)
        text = ResponseTransforms._CLOSING_FILLERS.sub("", text)
        # Fix leading whitespace / newlines after stripping
        text = text.strip()
        # Capitalize first character if needed
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        return text

    @staticmethod
    def confidence_boost(text: str) -> str:
        """Increase confidence language by removing qualifiers."""
        for pattern, replacement in ResponseTransforms._CONFIDENCE_BOOSTS:
            text = pattern.sub(replacement, text)
        return text

    @staticmethod
    def trading_mode(text: str) -> str:
        """Apply all transforms and surface trading actions to the top.

        Applies hedge_reduce + direct_mode + confidence_boost, then
        extracts BUY/SELL/HOLD actions with tickers/prices and moves
        them to the top of the response as bold action items.
        """
        # Apply base transforms
        text = ResponseTransforms.hedge_reduce(text)
        text = ResponseTransforms.direct_mode(text)
        text = ResponseTransforms.confidence_boost(text)

        # Extract trading actions
        actions = ResponseTransforms._TRADING_ACTION.findall(text)
        if not actions:
            return text

        # Build action header
        seen = set()
        action_lines = []
        for action, ticker, price in actions:
            action_upper = action.upper()
            ticker_upper = ticker.upper()
            key = f"{action_upper}-{ticker_upper}"
            if key in seen:
                continue
            seen.add(key)

            if price:
                action_lines.append(
                    f"**{action_upper} {ticker_upper} @ ${price}**"
                )
            else:
                action_lines.append(f"**{action_upper} {ticker_upper}**")

        if not action_lines:
            return text

        header = "\n".join(action_lines)
        return f"{header}\n\n---\n\n{text}"

    @staticmethod
    def apply(text: str, mode: str = "direct") -> str:
        """Apply a named transform or chain of transforms.

        Modes:
            - "direct": Strip preambles and filler (direct_mode)
            - "hedge": Remove hedging language (hedge_reduce)
            - "confidence": Boost confidence language (confidence_boost)
            - "trading": Full trading mode (all transforms + action extraction)
            - "full": Apply hedge_reduce + direct_mode + confidence_boost
        """
        transforms = {
            "direct": ResponseTransforms.direct_mode,
            "hedge": ResponseTransforms.hedge_reduce,
            "confidence": ResponseTransforms.confidence_boost,
            "trading": ResponseTransforms.trading_mode,
        }

        if mode == "full":
            text = ResponseTransforms.hedge_reduce(text)
            text = ResponseTransforms.direct_mode(text)
            text = ResponseTransforms.confidence_boost(text)
            return text

        transform = transforms.get(mode)
        if transform is None:
            raise ValueError(
                f"Unknown transform mode '{mode}'. "
                f"Available: {', '.join(list(transforms.keys()) + ['full'])}"
            )
        return transform(text)
