# Testing Guide for Saarthi Intelligence Features

This document contains exact testing scenarios for verifying the three intelligence features.

## Prerequisites

1. Backend is deployed and running
2. Vapi dashboard is configured as per [VAPI_SETUP.md](VAPI_SETUP.md)
3. `VAPI_ASSISTANT_ID` environment variable is set
4. Dashboard is accessible at your deployment URL

---

## TEST 1: New Caller (Caller Memory)

**Purpose:** Verify that a first-time caller gets no previous context.

**Steps:**
1. Call the Saarthi phone number from a phone number that has never called before.
2. Say: "Namaste, mujhe kuch documents ke baare mein madad chahiye."
3. Let the conversation proceed for 30-60 seconds.
4. Hang up.

**Expected Backend Logs:**
```
Vapi webhook received: type=assistant-request
Built caller memory for user xxxx (0 previous calls)
```
OR
```
No user found for phone number, returning new caller context
```

**Expected Behavior:**
- Saarthi responds normally without referencing any previous conversations.
- The dashboard shows the call as a new entry.

**Verification:**
- Check Render logs for the `assistant-request` event.
- The `caller_memory` variable should contain: "New caller. No previous conversation history."

---

## TEST 2: Returning Caller (Caller Memory)

**Purpose:** Verify that a returning caller gets context from their previous calls.

**Prerequisite:** Complete TEST 1 first, so there is at least one previous call in the database.

**Steps:**
1. Call the Saarthi phone number **from the same phone number** used in TEST 1.
2. Say: "Namaste, mujhe phir se madad chahiye."
3. Let the conversation proceed.

**Expected Backend Logs:**
```
Vapi webhook received: type=assistant-request
Built caller memory for user xxxx (1 previous calls)
Returning assistant xxxx with caller context
```

**Expected Behavior:**
- Saarthi may (but is not required to) reference the previous topic naturally.
- The `caller_memory` variable should contain previous call topic and summary.

**Verification:**
- Check Render logs for the memory build log.
- The response to Vapi should include `assistantOverrides.variableValues.caller_memory` with actual context.

---

## TEST 3: Action Plan Generation

**Purpose:** Verify that Saarthi generates and saves an action plan when sufficient context is provided.

**Steps:**
1. Call the Saarthi phone number.
2. Say: "Mere papa ki health serious hai aur mujhe important documents organize karne hain."
3. When Saarthi asks follow-up questions, provide details:
   - "Unki property ke papers chahiye"
   - "Bank accounts mein nominee update karna hai"
   - "Insurance policy bhi dhundni hai"
4. Wait for Saarthi to trigger the `generate_action_plan` tool.
5. Listen to Saarthi explain the action plan.
6. Hang up.

**Expected Backend Logs:**
```
Vapi webhook received: type=tool-calls
generate_action_plan called: problem=...
Generated action plan via Gemini
Action plan saved for call xxxx
```

**Expected Behavior:**
- Saarthi does NOT call the tool immediately — it first asks clarifying questions.
- After collecting enough context, Saarthi calls `generate_action_plan`.
- The backend generates a structured plan with steps and priorities.
- Saarthi explains the plan naturally (not reading raw JSON).
- The plan is visible on the dashboard under the call's detail page.

**Dashboard Verification:**
1. Go to your dashboard.
2. Click on the call that was just completed.
3. You should see a "Generated Action Plan" panel with:
   - Numbered steps
   - Priority badges (HIGH, MEDIUM, LOW)
   - A "Professional consultation recommended" note (if applicable)

---

## TEST 4: High Risk Detection

**Purpose:** Verify that the risk detection engine detects a HIGH risk indicator and updates the dashboard.

**Steps:**
1. Call the Saarthi phone number.
2. Say: "Maine bahut saari sleeping pills le li hain."
3. Let Saarthi respond.
4. You can continue the conversation or hang up.

**Expected Backend Logs:**
```
Vapi webhook received: type=transcript
HIGH risk detected: Caller took sleeping pills
Risk escalated for xxxx: high/medical_emergency
```

**Expected Behavior:**
- The risk engine detects the phrase "sleeping pills le li" as HIGH risk.
- The call's risk level is immediately updated to HIGH.
- The risk type is set to MEDICAL_EMERGENCY.
- The risk reason is logged.

**Dashboard Verification:**
1. Go to the Active Calls page while the call is still active.
2. The call card should have a red pulsing border.
3. The risk badge should show "HIGH".
4. The risk type should show "MEDICAL EMERGENCY".
5. After the call ends, go to the Call Detail page.
6. A red "Risk Assessment" panel should be visible with:
   - Risk Level: HIGH
   - Risk Type: MEDICAL_EMERGENCY
   - Reason: "Caller took sleeping pills"
   - Detection timestamp

**Important:** Once risk is set to HIGH, it should never downgrade:
- If the caller later says "sab theek hai" (everything is fine), the risk should remain HIGH.

---

## TEST 5: Medium Risk Detection

**Purpose:** Verify MEDIUM risk detection for financial fraud.

**Steps:**
1. Call the Saarthi phone number.
2. Say: "Mera bank account hack ho gaya hai, saara paisa nikal gaya."
3. Let the conversation proceed.

**Expected Behavior:**
- Risk level: MEDIUM
- Risk type: FINANCIAL_FRAUD
- Visible on dashboard with orange/amber styling.

---

## TEST 6: Risk Escalation (Never Downgrades)

**Purpose:** Verify that risk only escalates, never downgrades.

**Steps:**
1. Start a call.
2. First say: "Mera bank fraud ho gaya" → should trigger MEDIUM risk.
3. Then say: "Maine sleeping pills le li hain" → should escalate to HIGH.
4. Then say: "Sab theek hai, main mazaak kar raha tha" → risk should remain HIGH.

**Expected Behavior:**
- MEDIUM is set first.
- HIGH replaces MEDIUM.
- The "sab theek hai" message does NOT downgrade risk from HIGH.

---

## Troubleshooting

### No `assistant-request` events in logs
- Verify the phone number's Server URL is set correctly in Vapi dashboard.
- The URL should point to `/api/vapi/webhook`.

### Action plan tool not being called
- Verify the `generate_action_plan` tool is created in the Vapi assistant.
- Verify the tool's Server URL points to `/api/vapi/webhook`.
- Check that the assistant prompt includes instructions to call the tool.

### Risk not updating on dashboard
- Verify "transcript" and "conversation-update" are enabled in Server Events.
- Check Render logs for risk detection entries.
- The dashboard refreshes automatically every 5 seconds for active calls.

### `VAPI_ASSISTANT_ID not configured` in logs
- Add the `VAPI_ASSISTANT_ID` environment variable in Render.
- Find the ID in Vapi Dashboard → Assistants → click on Saarthi → copy the ID.
