"""
Action plan generator for Saarthi.

Generates structured, practical action plans during live calls.
Uses Gemini if available, with a rule-based fallback.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from saarthi.models.enums import CallTopic

logger = logging.getLogger(__name__)


def _rule_based_plan(
    problem: str,
    relevant_context: str,
    caller_goal: str,
    urgency: str,
) -> dict[str, Any]:
    """Generate an action plan using simple rule-based logic.

    This is the fallback when Gemini is not available.
    """
    problem_lower = problem.lower()
    context_lower = relevant_context.lower()
    goal_lower = caller_goal.lower()

    # Determine priority based on urgency
    base_priority = "MEDIUM"
    if urgency and urgency.lower() in ("high", "urgent", "critical"):
        base_priority = "HIGH"
    elif urgency and urgency.lower() in ("low", "not urgent"):
        base_priority = "LOW"

    action_items = []
    professional_help = False
    step = 1

    # Document-related keywords
    if any(kw in problem_lower + context_lower for kw in [
        "document", "dastavez", "kagaz", "paperwork", "certificate", "records",
        "property", "deed", "will", "nomination", "nominee"
    ]):
        action_items.extend([
            {"step": step, "title": "Collect all existing documents and organize them by category", "priority": base_priority},
            {"step": step + 1, "title": "Make photocopies and digital scans of all important documents", "priority": base_priority},
            {"step": step + 2, "title": "Verify all nominee and beneficiary details are up to date", "priority": "HIGH"},
        ])
        step += 3
        professional_help = True

    # Financial keywords
    elif any(kw in problem_lower + context_lower for kw in [
        "bank", "loan", "insurance", "policy", "investment", "paisa", "money",
        "emi", "credit", "debit", "account", "savings", "fd", "mutual fund"
    ]):
        action_items.extend([
            {"step": step, "title": "List all bank accounts and financial instruments", "priority": base_priority},
            {"step": step + 1, "title": "Verify nominee details for all accounts and policies", "priority": "HIGH"},
            {"step": step + 2, "title": "Consult a certified financial advisor for personalized guidance", "priority": base_priority},
        ])
        step += 3
        professional_help = True

    # Legal keywords
    elif any(kw in problem_lower + context_lower for kw in [
        "legal", "court", "case", "lawyer", "kanoon", "fir", "police",
        "dispute", "property dispute", "divorce", "custody", "tenant", "landlord"
    ]):
        action_items.extend([
            {"step": step, "title": "Gather all relevant legal documents and evidence", "priority": "HIGH"},
            {"step": step + 1, "title": "Consult a qualified lawyer in your area", "priority": "HIGH"},
            {"step": step + 2, "title": "Note down important dates and deadlines", "priority": base_priority},
        ])
        step += 3
        professional_help = True

    # Health keywords
    elif any(kw in problem_lower + context_lower for kw in [
        "health", "medical", "doctor", "hospital", "illness", "bimari",
        "treatment", "surgery", "medicine", "diagnosis"
    ]):
        action_items.extend([
            {"step": step, "title": "Consult a qualified medical professional immediately", "priority": "HIGH"},
            {"step": step + 1, "title": "Collect all medical reports and prescriptions", "priority": base_priority},
            {"step": step + 2, "title": "Check eligibility for government health schemes (Ayushman Bharat, etc.)", "priority": base_priority},
        ])
        step += 3
        professional_help = True

    # Government services
    elif any(kw in problem_lower + context_lower for kw in [
        "government", "sarkari", "scheme", "yojana", "ration", "aadhar",
        "pan", "passport", "voter id", "pension", "subsidy"
    ]):
        action_items.extend([
            {"step": step, "title": "Visit the nearest government office or Common Service Centre (CSC)", "priority": base_priority},
            {"step": step + 1, "title": "Prepare required identity documents (Aadhar, PAN, etc.)", "priority": base_priority},
            {"step": step + 2, "title": "Check eligibility on the official government website or helpline", "priority": base_priority},
        ])
        step += 3

    # Default fallback
    else:
        action_items.extend([
            {"step": step, "title": "Write down the key details of your situation clearly", "priority": base_priority},
            {"step": step + 1, "title": "Identify the right professional or office to consult", "priority": base_priority},
            {"step": step + 2, "title": "Prepare relevant documents before your visit", "priority": base_priority},
        ])
        step += 3

    # Add goal-specific step if goal is provided
    if caller_goal:
        action_items.append({
            "step": step,
            "title": f"Focus on achieving your goal: {caller_goal[:100]}",
            "priority": base_priority,
        })

    summary = f"Action plan for: {problem[:150]}"
    if caller_goal:
        summary += f". Goal: {caller_goal[:100]}"

    return {
        "summary": summary,
        "action_items": action_items[:6],  # Cap at 6 items
        "professional_help_recommended": professional_help,
    }


async def generate_action_plan(
    problem: str,
    relevant_context: str,
    caller_goal: str,
    urgency: str,
    analyzer=None,
) -> dict[str, Any]:
    """Generate a structured action plan.

    Uses Gemini via the existing analyzer if available,
    falls back to rule-based generation.

    Args:
        problem: The caller's main problem.
        relevant_context: Context about their situation.
        caller_goal: What the caller wants to achieve.
        urgency: How urgent the matter is.
        analyzer: Optional CallAnalyzer instance for Gemini-based generation.

    Returns:
        A dict with summary, action_items, and professional_help_recommended.
    """
    # Try Gemini-based generation first
    if analyzer:
        try:
            prompt = f"""Generate a practical, step-by-step action plan for this caller.

PROBLEM: {problem}
CONTEXT: {relevant_context}
CALLER'S GOAL: {caller_goal}
URGENCY: {urgency}

Return a JSON object with:
- "summary": one-sentence summary of the plan
- "action_items": array of objects with "step" (number), "title" (string), "priority" ("HIGH", "MEDIUM", or "LOW")
- "professional_help_recommended": boolean

Keep it practical and actionable. Max 6 steps. Output ONLY valid JSON."""

            response = await asyncio.to_thread(
                analyzer._client.models.generate_content,
                model=analyzer._model_name,
                contents=prompt,
                config=__import__("google.genai.types", fromlist=["types"]).GenerateContentConfig(
                    temperature=0.3,
                    response_mime_type="application/json",
                ),
            )

            raw_json = response.text.strip()
            raw_json = re.sub(r"^```(?:json)?\s*", "", raw_json)
            raw_json = re.sub(r"\s*```$", "", raw_json)
            plan = json.loads(raw_json)

            # Validate structure
            if "action_items" in plan and isinstance(plan["action_items"], list):
                logger.info("Generated action plan via Gemini")
                return plan

        except Exception as e:
            logger.warning("Gemini action plan generation failed, using fallback: %s", e)

    # Fallback to rule-based
    plan = _rule_based_plan(problem, relevant_context, caller_goal, urgency)
    logger.info("Generated action plan via rule-based fallback")
    return plan
