"""
Real-time risk detection engine for Saarthi.

Uses rule-based keyword and phrase matching in Hindi, Hinglish, and English
to detect risk indicators during live conversations. This is a practical,
explainable prototype — not a fake AI safety system.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from saarthi.models.enums import RiskLevel, RiskType

logger = logging.getLogger(__name__)


@dataclass
class RiskResult:
    """Result of a risk detection analysis."""

    level: RiskLevel
    risk_type: RiskType
    reason: str


# ---------------------------------------------------------------------------
# HIGH risk patterns — immediate danger, self-harm, suicide, violence
# ---------------------------------------------------------------------------

HIGH_RISK_PATTERNS: list[tuple[str, RiskType, str]] = [
    # Suicide / Self-harm — Hindi
    (r"main?\s*marna\s*chahta\s*hoo[n]?", RiskType.SUICIDE, "Caller expressed desire to die (Hindi)"),
    (r"main?\s*marna\s*chahti\s*hoo[n]?", RiskType.SUICIDE, "Caller expressed desire to die (Hindi)"),
    (r"mujhe?\s*mar\s*jana\s*hai", RiskType.SUICIDE, "Caller wants to die (Hindi)"),
    (r"main?\s*suicide\s*karna?\s*chaht[ai]", RiskType.SUICIDE, "Caller mentioned suicide intent (Hinglish)"),
    (r"zindagi\s*se\s*tang\s*aa?\s*gaya", RiskType.SELF_HARM, "Caller exhausted with life (Hindi)"),
    (r"zindagi\s*se\s*tang\s*aa?\s*gayi", RiskType.SELF_HARM, "Caller exhausted with life (Hindi)"),
    (r"jeene\s*ka\s*mann?\s*nahi", RiskType.SUICIDE, "Caller has no will to live (Hindi)"),
    (r"khatam\s*karna?\s*chaht[ai]", RiskType.SUICIDE, "Caller wants to end it (Hindi)"),

    # Self-harm — pills / poison / cutting
    (r"sleeping\s*pills?\s*le\s*li", RiskType.MEDICAL_EMERGENCY, "Caller took sleeping pills"),
    (r"pills?\s*kha\s*li", RiskType.MEDICAL_EMERGENCY, "Caller consumed pills (Hindi)"),
    (r"zeher\s*kha\s*liya", RiskType.MEDICAL_EMERGENCY, "Caller ingested poison (Hindi)"),
    (r"poison\s*le?\s*liy[ae]", RiskType.MEDICAL_EMERGENCY, "Caller took poison (Hinglish)"),
    (r"apn[ie]\s*nass?\s*kaat", RiskType.SELF_HARM, "Caller cut wrists (Hindi)"),
    (r"cut\s*(myself|my\s*wrist)", RiskType.SELF_HARM, "Caller mentioned self-cutting (English)"),
    (r"overdose\s*(le\s*li|liya|taken)", RiskType.MEDICAL_EMERGENCY, "Overdose mentioned"),

    # Violence / weapons
    (r"mere?\s*paas\s*weapon\s*hai", RiskType.VIOLENCE, "Caller has a weapon (Hinglish)"),
    (r"mere?\s*paas\s*bandook\s*hai", RiskType.VIOLENCE, "Caller has a gun (Hindi)"),
    (r"mere?\s*paas\s*chaaku\s*hai", RiskType.VIOLENCE, "Caller has a knife (Hindi)"),
    (r"koi\s*mujhe?\s*maar\s*raha", RiskType.VIOLENCE, "Caller being beaten (Hindi)"),
    (r"mujhe?\s*maar\s*dega", RiskType.VIOLENCE, "Threat of being killed (Hindi)"),
    (r"jaan\s*se\s*maar\s*d[eu]", RiskType.VIOLENCE, "Death threat detected (Hindi)"),

    # Medical emergency
    (r"bahut\s*bleeding\s*ho\s*rahi", RiskType.MEDICAL_EMERGENCY, "Heavy bleeding reported (Hinglish)"),
    (r"bahut\s*khoon\s*nikal\s*raha", RiskType.MEDICAL_EMERGENCY, "Heavy bleeding reported (Hindi)"),
    (r"heart\s*attack\s*aa\s*raha", RiskType.MEDICAL_EMERGENCY, "Heart attack symptoms (Hinglish)"),
    (r"saans\s*nahi\s*aa\s*rah[ai]", RiskType.MEDICAL_EMERGENCY, "Breathing difficulty (Hindi)"),
    (r"can'?t\s*breathe?", RiskType.MEDICAL_EMERGENCY, "Breathing difficulty (English)"),
    (r"behosh\s*ho\s*rah[ae]", RiskType.MEDICAL_EMERGENCY, "Losing consciousness (Hindi)"),

    # Immediate danger
    (r"aag\s*lag\s*gayi", RiskType.IMMEDIATE_DANGER, "Fire emergency (Hindi)"),
    (r"ghar\s*me\s*aag", RiskType.IMMEDIATE_DANGER, "House fire (Hindi)"),

    # English direct
    (r"i\s*want\s*to\s*(die|kill\s*myself)", RiskType.SUICIDE, "Suicidal intent expressed (English)"),
    (r"going\s*to\s*(end\s*it|kill\s*myself)", RiskType.SUICIDE, "Suicidal plan expressed (English)"),
    (r"i'?m\s*going\s*to\s*hurt\s*myself", RiskType.SELF_HARM, "Self-harm intent (English)"),
]


# ---------------------------------------------------------------------------
# MEDIUM risk patterns — distress, fraud, legal urgency
# ---------------------------------------------------------------------------

MEDIUM_RISK_PATTERNS: list[tuple[str, RiskType, str]] = [
    # Financial fraud
    (r"paisa\s*loot\s*liya", RiskType.FINANCIAL_FRAUD, "Financial fraud reported (Hindi)"),
    (r"fraud\s*ho\s*gaya", RiskType.FINANCIAL_FRAUD, "Fraud reported (Hinglish)"),
    (r"scam\s*(ho\s*gaya|kiya)", RiskType.FINANCIAL_FRAUD, "Scam reported (Hinglish)"),
    (r"bank\s*se\s*paisa?\s*(nikal|chori)", RiskType.FINANCIAL_FRAUD, "Bank theft reported (Hindi)"),
    (r"account\s*hack", RiskType.FINANCIAL_FRAUD, "Account hacked (Hinglish)"),
    (r"upi\s*(se\s*)?paisa?\s*(kat|chori)", RiskType.FINANCIAL_FRAUD, "UPI fraud reported (Hinglish)"),

    # Legal urgency
    (r"arrest\s*ho\s*(sakta|jayega)", RiskType.LEGAL_URGENCY, "Arrest risk reported (Hinglish)"),
    (r"jail\s*(bhej|jaana|ho\s*jayega)", RiskType.LEGAL_URGENCY, "Jail threat reported (Hinglish)"),
    (r"court\s*(ka\s*notice|se\s*summon)", RiskType.LEGAL_URGENCY, "Court notice received (Hinglish)"),
    (r"police\s*(aa?\s*rah[ai]|pakad)", RiskType.LEGAL_URGENCY, "Police involvement (Hinglish)"),
    (r"fir\s*darj\s*ho", RiskType.LEGAL_URGENCY, "FIR filing reported (Hindi)"),

    # Severe emotional distress (without explicit self-harm)
    (r"bahut\s*dar[r]?\s*lag\s*raha", RiskType.NONE, "Severe fear reported (Hindi)"),
    (r"bahut\s*tension\s*me\s*hoo[n]?", RiskType.NONE, "Severe stress reported (Hinglish)"),
    (r"koi\s*rasta\s*nahi\s*(dikh|mil)\s*rah[ai]", RiskType.NONE, "Feeling helpless/trapped (Hindi)"),
    (r"i'?m\s*(very\s*)?scared", RiskType.NONE, "Fear expressed (English)"),
    (r"domestic\s*violence", RiskType.VIOLENCE, "Domestic violence reported (English)"),
    (r"ghar\s*me\s*maarpeet", RiskType.VIOLENCE, "Domestic violence reported (Hindi)"),
]


class RiskDetector:
    """Rule-based risk detection engine.

    Scans conversation text for high and medium risk indicators in
    Hindi, Hinglish, and English. Results only escalate — never downgrade.
    """

    def detect(self, text: str) -> RiskResult:
        """Analyze text for risk indicators.

        Args:
            text: The conversation text to analyze (can be a single
                  transcript segment or the entire conversation).

        Returns:
            RiskResult with the highest detected risk level, type, and reason.
        """
        if not text or len(text.strip()) < 5:
            return RiskResult(
                level=RiskLevel.LOW,
                risk_type=RiskType.NONE,
                reason="",
            )

        normalized = text.lower().strip()

        # Check HIGH risk patterns first
        for pattern, risk_type, reason in HIGH_RISK_PATTERNS:
            if re.search(pattern, normalized, re.IGNORECASE):
                logger.warning("HIGH risk detected: %s", reason)
                return RiskResult(
                    level=RiskLevel.HIGH,
                    risk_type=risk_type,
                    reason=reason,
                )

        # Check MEDIUM risk patterns
        for pattern, risk_type, reason in MEDIUM_RISK_PATTERNS:
            if re.search(pattern, normalized, re.IGNORECASE):
                logger.warning("MEDIUM risk detected: %s", reason)
                return RiskResult(
                    level=RiskLevel.MEDIUM,
                    risk_type=risk_type if risk_type != RiskType.NONE else RiskType.NONE,
                    reason=reason,
                )

        return RiskResult(
            level=RiskLevel.LOW,
            risk_type=RiskType.NONE,
            reason="",
        )
