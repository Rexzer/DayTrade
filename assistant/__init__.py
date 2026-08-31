"""Data-grounded AI trading assistant (Phase 8).

Answers questions about the CURRENT system state using ONLY the data the
platform actually has. It never invents prices, indicators, trades, news,
broker information or performance statistics. When the required data is
unavailable it replies "INSUFFICIENT DATA" and says what is missing.

It is deliberately a transparent, rule/intent-based explainer rather than a
black box — every answer is traceable to the data sources it cites, and it
never represents a signal score as a probability of profit.
"""

from assistant.assistant import AssistantAnswer, TradingAssistant
from assistant.context import AssistantContext

__all__ = ["AssistantContext", "AssistantAnswer", "TradingAssistant"]
