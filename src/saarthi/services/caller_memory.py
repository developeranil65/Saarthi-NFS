"""
Caller memory builder for Saarthi.

Constructs compact caller context from previous call history,
designed to be injected as a dynamic variable into the Vapi assistant prompt.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def format_topic(topic: str) -> str:
    """Convert a topic enum value to a human-readable string."""
    topic_map = {
        "document_guidance": "Document Guidance",
        "government_services": "Government Services",
        "career_guidance": "Career Guidance",
        "education": "Education",
        "financial_info": "Financial Planning",
        "legal_info": "Legal Matters",
        "health_info": "Health Guidance",
        "technology": "Technology Help",
        "general_guidance": "General Guidance",
        "other": "General Discussion",
    }
    return topic_map.get(topic, topic.replace("_", " ").title())


def build_caller_memory(call_history: list[dict[str, Any]]) -> str:
    """Build compact caller memory from previous call history.

    Args:
        call_history: List of dicts with topic, summary, action_items, start_time.
                      Ordered by most recent first.

    Returns:
        A formatted string suitable for the {{caller_memory}} variable.
        Returns a "new caller" message if no history exists.
    """
    if not call_history:
        return "New caller. No previous conversation history."

    parts = ["CALLER CONTEXT:"]
    parts.append(f"Previous interactions: {len(call_history)}")
    parts.append("")

    # Most recent call gets detailed treatment
    latest = call_history[0]
    topic = format_topic(latest.get("topic", "other"))
    summary = latest.get("summary", "").strip()

    parts.append(f"Most recent topic: {topic}")
    if summary:
        # Truncate long summaries
        if len(summary) > 250:
            summary = summary[:247] + "..."
        parts.append(f"Last summary: {summary}")

    # Collect pending action items from all recent calls
    all_action_items = []
    for call in call_history:
        items = call.get("action_items", [])
        if isinstance(items, list):
            all_action_items.extend(items)

    if all_action_items:
        # Deduplicate and cap at 5
        seen = set()
        unique_items = []
        for item in all_action_items:
            item_str = str(item).strip()
            item_lower = item_str.lower()
            if item_lower not in seen and item_str:
                seen.add(item_lower)
                unique_items.append(item_str)
                if len(unique_items) >= 5:
                    break

        if unique_items:
            parts.append("Pending action items:")
            for item in unique_items:
                parts.append(f"- {item}")

    # Previous topics (if multiple calls)
    if len(call_history) > 1:
        previous_topics = []
        seen_topics = set()
        for call in call_history[1:]:
            t = format_topic(call.get("topic", "other"))
            if t not in seen_topics:
                seen_topics.add(t)
                previous_topics.append(t)
        if previous_topics:
            parts.append(f"Other previous topics: {', '.join(previous_topics[:3])}")

    return "\n".join(parts)
