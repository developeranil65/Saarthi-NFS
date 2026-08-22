"""
Core enumerations for Saarthi.

Defines the bounded vocabulary for call statuses, topics,
risk levels, and message roles used across all components.
"""

from enum import StrEnum


class CallStatus(StrEnum):
    """Status of a call through its lifecycle."""

    INCOMING = "incoming"
    ACTIVE = "active"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class CallTopic(StrEnum):
    """Topic categories for call classification."""

    DOCUMENT_GUIDANCE = "document_guidance"
    GOVERNMENT_SERVICES = "government_services"
    CAREER_GUIDANCE = "career_guidance"
    EDUCATION = "education"
    FINANCIAL_INFO = "financial_info"
    LEGAL_INFO = "legal_info"
    HEALTH_INFO = "health_info"
    TECHNOLOGY = "technology"
    GENERAL_GUIDANCE = "general_guidance"
    OTHER = "other"


class RiskLevel(StrEnum):
    """Risk classification for calls."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskType(StrEnum):
    """Specific risk type detected during a call."""

    NONE = "none"
    SELF_HARM = "self_harm"
    SUICIDE = "suicide"
    MEDICAL_EMERGENCY = "medical_emergency"
    VIOLENCE = "violence"
    IMMEDIATE_DANGER = "immediate_danger"
    FINANCIAL_FRAUD = "financial_fraud"
    LEGAL_URGENCY = "legal_urgency"


class MessageRole(StrEnum):
    """Role of a conversation message participant."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
