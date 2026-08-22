"""Vapi Webhook endpoints for Saarthi.

Handles incoming call lifecycle events from the external Vapi voice agent,
such as call started, status updates, transcripts, and end-of-call reports.

Intelligence features:
- assistant-request: Returns caller memory as dynamic variables
- tool-calls: Handles generate_action_plan tool calls
- transcript: Real-time risk detection
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from saarthi.core import state
from saarthi.models.core import Call, ConversationMessage
from saarthi.models.enums import CallStatus, CallTopic, MessageRole, RiskLevel, RiskType
from saarthi.services.risk_detector import RiskDetector
from saarthi.services.caller_memory import build_caller_memory
from saarthi.services.action_plan_generator import generate_action_plan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vapi", tags=["Webhooks"])

# Singleton risk detector
_risk_detector = RiskDetector()


@router.post("/webhook")
async def vapi_webhook(request: Request) -> JSONResponse:
    """Receive and process Vapi call lifecycle events.

    Handles the following core flows:
    1. 'assistant-request': Returns the existing assistant with caller context.
    2. 'call-started' / 'status-update' (in-progress): Creates or updates an active call record.
    3. 'transcript': Real-time risk detection on live conversation.
    4. 'tool-calls': Handles custom tool calls (generate_action_plan).
    5. 'end-of-call-report' / 'hang': Finalizes the call, processes the transcript, and triggers AI analysis.

    Args:
        request: The incoming FastAPI request containing the JSON payload from Vapi.

    Returns:
        JSONResponse indicating success or failure. Always returns 200 on handled logic
        errors to prevent Vapi from continuously retrying the same payload.
    """
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    # Vapi sends events wrapped in a "message" object depending on the webhook type
    message = payload.get("message", payload)
    event_type = message.get("type", "")

    logger.info("Vapi webhook received: type=%s", event_type)

    if state.db is None:
        logger.error("Database is not initialized. Cannot process webhook.")
        return JSONResponse({"status": "error", "detail": "Database unavailable"})

    try:
        # --- Feature 1: Assistant Request (Caller Memory) ---
        if event_type == "assistant-request":
            return await _handle_assistant_request(message)

        # --- Feature 2: Tool Calls (Action Plan) ---
        elif event_type == "tool-calls":
            return await _handle_tool_calls(message)

        # --- Existing: Call Started ---
        elif event_type in ("call-started", "status-update"):
            await _handle_call_started(message)

        # --- Existing: Call Ended ---
        elif event_type in ("end-of-call-report", "hang"):
            await _handle_call_ended(message)

        # --- Feature 3: Transcript (Risk Detection) ---
        elif event_type == "transcript":
            await _handle_transcript(message)

        # --- Conversation update (contains transcript segments) ---
        elif event_type == "conversation-update":
            await _handle_conversation_update(message)

        else:
            logger.debug("Unhandled Vapi event type: %s", event_type)

    except Exception as e:
        logger.error("Error processing Vapi webhook: %s", e, exc_info=True)
        # Return 200 even on error to prevent Vapi from retrying
        return JSONResponse({"status": "error", "detail": str(e)})

    return JSONResponse({"status": "ok"})


# ====================================================================
# FEATURE 1: Assistant Request — Caller Memory
# ====================================================================

async def _handle_assistant_request(message: dict[str, Any]) -> JSONResponse:
    """Handle assistant-request from Vapi.

    Looks up the caller's previous call history and returns the existing
    Saarthi assistant ID with caller_memory as a dynamic variable.
    """
    call_data = message.get("call", message)
    customer = call_data.get("customer", {})
    phone_number = customer.get("number", "")

    logger.info("Assistant request for phone: %s", phone_number[:6] + "****" if len(phone_number) > 6 else phone_number)

    # Get assistant ID from config
    assistant_id = ""
    if state.config:
        assistant_id = state.config.vapi_assistant_id

    if not assistant_id:
        logger.warning("VAPI_ASSISTANT_ID not configured. Returning empty response.")
        return JSONResponse({"error": "Assistant not configured"}, status_code=200)

    # Build caller memory
    caller_memory = "New caller. No previous conversation history."

    if phone_number and state.db:
        try:
            user = await state.db.get_user_by_phone(phone_number)
            if user:
                history = await state.db.get_user_call_history(user.id, limit=5)
                caller_memory = build_caller_memory(history)
                logger.info("Built caller memory for user %s (%d previous calls)", user.id[:8], len(history))
        except Exception as e:
            logger.error("Failed to build caller memory: %s", e)

    # Return the assistant selector response
    response = {
        "assistantId": assistant_id,
        "assistantOverrides": {
            "variableValues": {
                "caller_memory": caller_memory,
            }
        }
    }

    logger.info("Returning assistant %s with caller context", assistant_id[:8])
    return JSONResponse(response)


# ====================================================================
# FEATURE 2: Tool Calls — Action Plan Generator
# ====================================================================

async def _handle_tool_calls(message: dict[str, Any]) -> JSONResponse:
    """Handle tool-calls event from Vapi.

    Processes the generate_action_plan function call, generates a plan,
    saves it to the database, and returns the result to Vapi.
    """
    call_data = message.get("call", message)
    vapi_call_id = call_data.get("id", "")

    tool_calls = message.get("toolCallList", message.get("toolCalls", []))
    if not tool_calls and "toolWithToolCallList" in message:
        # Some Vapi versions wrap it
        tool_calls = [
            item.get("toolCall") for item in message["toolWithToolCallList"] 
            if isinstance(item, dict) and "toolCall" in item
        ]
        
    if not tool_calls:
        return JSONResponse({"status": "ok"})

    results = []

    for tool_call in tool_calls:
        tool_call_id = tool_call.get("id", "")
        function_info = tool_call.get("function", tool_call)
        function_name = function_info.get("name", "")

        if function_name == "generate_action_plan":
            # Extract arguments
            args_raw = function_info.get("arguments", {})
            if isinstance(args_raw, str):
                try:
                    args = json.loads(args_raw)
                except json.JSONDecodeError:
                    args = {}
            else:
                args = args_raw or {}

            problem = args.get("problem", "")
            relevant_context = args.get("relevant_context", "")
            caller_goal = args.get("caller_goal", "")
            urgency = args.get("urgency", "medium")

            logger.info("generate_action_plan called: problem=%s", problem[:80])

            # Generate action plan
            plan = await generate_action_plan(
                problem=problem,
                relevant_context=relevant_context,
                caller_goal=caller_goal,
                urgency=urgency,
                analyzer=state.analyzer,
            )

            # Save to database
            if vapi_call_id and state.db:
                try:
                    await state.db.update_call_action_plan(vapi_call_id, plan)
                    logger.info("Action plan saved for call %s", vapi_call_id[:12])
                except Exception as e:
                    logger.error("Failed to save action plan: %s", e)

            # Format result for Vapi
            results.append({
                "toolCallId": tool_call_id,
                "result": json.dumps(plan),
            })
        else:
            logger.debug("Unknown tool call: %s", function_name)
            results.append({
                "toolCallId": tool_call_id,
                "result": json.dumps({"error": f"Unknown function: {function_name}"}),
            })

    return JSONResponse({"results": results})


# ====================================================================
# FEATURE 3: Real-Time Risk Detection
# ====================================================================

async def _handle_transcript(message: dict[str, Any]) -> None:
    """Handle real-time transcript events for risk detection.

    Analyzes the transcript text for risk indicators and updates
    the call's risk level in the database.
    """
    call_data = message.get("call", message)
    vapi_call_id = call_data.get("id", "")

    if not vapi_call_id:
        return

    # Extract transcript text
    transcript_text = message.get("transcript", "")

    # Also check the role — only analyze user/customer messages for risk
    role = message.get("role", "")
    if role in ("assistant", "bot", "ai"):
        return  # Don't flag AI responses as risks

    if not transcript_text:
        return

    # Run risk detection
    risk_result = _risk_detector.detect(transcript_text)

    # Only update if meaningful risk found
    if risk_result.level != RiskLevel.LOW and state.db:
        try:
            await state.db.update_call_risk(
                vapi_call_id=vapi_call_id,
                risk_level=risk_result.level,
                risk_type=risk_result.risk_type,
                risk_reason=risk_result.reason,
            )
        except Exception as e:
            logger.error("Failed to update risk for call %s: %s", vapi_call_id, e)


async def _handle_conversation_update(message: dict[str, Any]) -> None:
    """Handle conversation-update events for risk detection.

    These contain the full conversation so far. We analyze the latest
    messages for risk indicators.
    """
    call_data = message.get("call", message)
    vapi_call_id = call_data.get("id", "")

    if not vapi_call_id:
        return

    # Get the conversation messages
    messages_list = message.get("messages", message.get("artifact", {}).get("messages", []))
    if not messages_list:
        return

    # Analyze only user/customer messages for risk
    user_texts = []
    for msg in messages_list:
        role = msg.get("role", "")
        content = msg.get("content", msg.get("message", ""))
        if role in ("user", "customer") and content:
            user_texts.append(content)

    if not user_texts:
        return

    # Analyze combined user text
    combined_text = " ".join(user_texts)
    risk_result = _risk_detector.detect(combined_text)

    if risk_result.level != RiskLevel.LOW and state.db:
        try:
            await state.db.update_call_risk(
                vapi_call_id=vapi_call_id,
                risk_level=risk_result.level,
                risk_type=risk_result.risk_type,
                risk_reason=risk_result.reason,
            )
        except Exception as e:
            logger.error("Failed to update risk from conversation-update: %s", e)


# ====================================================================
# EXISTING: Call Started
# ====================================================================

async def _handle_call_started(message: dict[str, Any]) -> None:
    """Handle a call-started or status-update event from Vapi.

    Creates a new user if they don't exist, and initializes a new call record
    marked as ACTIVE.

    Args:
        message: The webhook message payload.
    """
    call_data = message.get("call", message)
    vapi_call_id = call_data.get("id", "")
    if not vapi_call_id:
        logger.warning("No call ID in call-started event")
        return

    # Check if call already exists to prevent duplicates
    # state.db is guaranteed to be initialized here due to the check in the main route
    existing = await state.db.get_call_by_vapi_id(vapi_call_id) # type: ignore
    if existing:
        # Update status to active
        await state.db.update_call(vapi_call_id, status=CallStatus.ACTIVE) # type: ignore
        return

    # Extract caller phone number from the nested customer object
    customer = call_data.get("customer", {})
    phone_number = customer.get("number", "unknown")

    # Create or get user
    user = await state.db.create_or_get_user(phone_number) # type: ignore

    # Parse start time, fallback to current UTC time if parsing fails
    started_at = call_data.get("startedAt", call_data.get("createdAt", ""))
    try:
        start_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        start_time = datetime.utcnow()

    # Create call record
    call = Call(
        vapi_call_id=vapi_call_id,
        user_id=user.id,
        status=CallStatus.ACTIVE,
        start_time=start_time,
    )
    await state.db.create_call(call) # type: ignore
    await state.db.increment_user_calls(user.id) # type: ignore

    logger.info("Call started: vapi_id=%s, caller=%s", vapi_call_id, user.masked_phone)


# ====================================================================
# EXISTING: Call Ended
# ====================================================================

async def _handle_call_ended(message: dict[str, Any]) -> None:
    """Handle end-of-call-report or hang event from Vapi.

    Finalizes the call duration, parses the transcript messages, and runs the
    AI CallAnalyzer to generate a summary, topic, risk level, and action items.

    Args:
        message: The webhook message payload containing the end-of-call data.
    """
    call_data = message.get("call", message)
    vapi_call_id = call_data.get("id", "")
    if not vapi_call_id:
        logger.warning("No call ID in call-ended event")
        return

    # Ensure call record exists (in case we missed the call-started webhook)
    existing = await state.db.get_call_by_vapi_id(vapi_call_id) # type: ignore
    if not existing:
        # Create a minimal record if we missed the start event
        customer = call_data.get("customer", {})
        phone_number = customer.get("number", "unknown")
        user = await state.db.create_or_get_user(phone_number) # type: ignore

        started_at = call_data.get("startedAt", call_data.get("createdAt", ""))
        try:
            start_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            start_time = datetime.utcnow()

        call = Call(
            vapi_call_id=vapi_call_id,
            user_id=user.id,
            status=CallStatus.PROCESSING,
            start_time=start_time,
        )
        await state.db.create_call(call) # type: ignore
        await state.db.increment_user_calls(user.id) # type: ignore

    # Calculate duration
    ended_at = call_data.get("endedAt", "")
    started_at = call_data.get("startedAt", "")
    duration = 0.0

    try:
        if ended_at and started_at:
            end_dt = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
            start_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            duration = (end_dt - start_dt).total_seconds()
        else:
            duration = call_data.get("duration", call_data.get("costBreakdown", {}).get("duration", 0.0))
    except (ValueError, AttributeError):
        pass

    # Extract transcript and individual messages
    transcript = ""
    messages_list = message.get("messages", message.get("artifact", {}).get("messages", []))

    conversation_messages = []
    if messages_list:
        transcript_parts = []
        for msg in messages_list:
            role_str = msg.get("role", "system")
            content = msg.get("content", msg.get("message", ""))
            if not content:
                continue

            # Map the Vapi role string to our internal MessageRole enum
            if role_str in ("user", "customer"):
                role = MessageRole.USER
                transcript_parts.append(f"USER: {content}")
            elif role_str in ("assistant", "bot", "ai"):
                role = MessageRole.ASSISTANT
                transcript_parts.append(f"AI: {content}")
            else:
                role = MessageRole.SYSTEM
                transcript_parts.append(f"SYSTEM: {content}")

            # Parse timestamp of the individual message
            msg_time_str = msg.get("time", msg.get("timestamp", ""))
            try:
                msg_time = datetime.fromisoformat(str(msg_time_str).replace("Z", "+00:00")) if msg_time_str else datetime.utcnow()
            except (ValueError, TypeError):
                msg_time = datetime.utcnow()

            # Append to conversation messages list to be saved in DB
            call_record = await state.db.get_call_by_vapi_id(vapi_call_id) # type: ignore
            if call_record:
                conversation_messages.append(
                    ConversationMessage(
                        call_id=call_record.id,
                        role=role,
                        content=content,
                        timestamp=msg_time,
                    )
                )

        transcript = "\n".join(transcript_parts)

    # Fallback to direct transcript string if message array was empty
    if not transcript:
        transcript = (
            message.get("transcript", "")
            or message.get("artifact", {}).get("transcript", "")
            or call_data.get("transcript", "")
        )

    # Extract recording URL
    recording_url = (
        message.get("recordingUrl", "")
        or message.get("artifact", {}).get("recordingUrl", "")
        or call_data.get("recordingUrl", "")
        or None
    )

    # Extract any pre-existing analysis from Vapi (if available)
    vapi_analysis = message.get("analysis", message.get("artifact", {}).get("analysis", {}))
    summary = ""
    topic = CallTopic.OTHER
    risk_level = RiskLevel.LOW
    action_items = []

    if vapi_analysis:
        summary = vapi_analysis.get("summary", "")
        structured = vapi_analysis.get("structuredData", {})
        if structured:
            topic_str = structured.get("topic", "")
            risk_str = structured.get("risk_level", structured.get("riskLevel", ""))
            action_items = structured.get("action_items", structured.get("actionItems", []))
            try:
                topic = CallTopic(topic_str.lower())
            except (ValueError, AttributeError):
                pass
            try:
                risk_level = RiskLevel(risk_str.lower())
            except (ValueError, AttributeError):
                pass

    # Initial update of call record with duration and transcript
    update_data = {
        "status": CallStatus.PROCESSING,
        "duration_seconds": duration,
        "transcript": transcript,
    }

    if ended_at:
        try:
            update_data["end_time"] = datetime.fromisoformat(ended_at.replace("Z", "+00:00")) # type: ignore
        except (ValueError, AttributeError):
            update_data["end_time"] = datetime.utcnow() # type: ignore
    else:
        update_data["end_time"] = datetime.utcnow() # type: ignore

    if recording_url:
        update_data["recording_url"] = recording_url

    await state.db.update_call(vapi_call_id, **update_data) # type: ignore

    # Store individual conversation messages
    if conversation_messages:
        await state.db.create_messages(conversation_messages) # type: ignore

    # Run AI analysis via Gemini to get topic, risk, and action items
    # We do this even if Vapi provided a basic summary, because we need structured data
    if transcript and state.analyzer:
        try:
            analysis = await state.analyzer.analyze(transcript)
            summary = analysis.summary
            topic = analysis.topic
            risk_level = analysis.risk_level
            action_items = analysis.action_items
        except Exception as e:
            logger.error("Call analysis failed: %s", e)

    # Final risk check on full transcript (may escalate risk from real-time detection)
    if transcript:
        final_risk = _risk_detector.detect(transcript)
        if final_risk.level != RiskLevel.LOW:
            # Use the higher of the two risk levels
            risk_order = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}
            if risk_order.get(final_risk.level, 0) > risk_order.get(risk_level, 0):
                risk_level = final_risk.level

    # Final update with AI analysis results
    analysis_data = {
        "status": CallStatus.COMPLETED,
        "summary": summary,
        "topic": topic,
        "risk_level": risk_level,
        "action_items": action_items,
    }
    await state.db.update_call(vapi_call_id, **analysis_data) # type: ignore

    logger.info(
        "Call completed: vapi_id=%s, duration=%.0fs, topic=%s, risk=%s",
        vapi_call_id,
        duration,
        topic.value,
        risk_level.value,
    )
