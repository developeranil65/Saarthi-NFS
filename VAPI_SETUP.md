# VAPI Configuration Guide for Saarthi Intelligence Features

This document contains the exact manual steps required in the Vapi dashboard to enable the three intelligence features.

## Prerequisites

- Your Saarthi backend is deployed and accessible (e.g., `https://your-app.onrender.com`)
- You have access to the Vapi dashboard at https://dashboard.vapi.ai
- Your Saarthi phone number is already connected to a Vapi assistant

---

## Step 1: Get Your Assistant ID

1. Go to **Vapi Dashboard → Assistants**
2. Click on your **Saarthi** assistant
3. Copy the **Assistant ID** from the URL or the settings panel
   - It looks like: `a1b2c3d4-e5f6-7890-abcd-ef1234567890`
4. Add it as an environment variable in your deployment:
   ```
   VAPI_ASSISTANT_ID=a1b2c3d4-e5f6-7890-abcd-ef1234567890
   ```
   - On Render: Go to your service → Environment → Add the variable

---

## Step 2: Configure Phone Number for Assistant Selector

This enables **Feature 1: Caller Memory**.

1. Go to **Vapi Dashboard → Phone Numbers**
2. Click on the Saarthi phone number
3. Under **Inbound Settings**, change **Assistant** to **Server URL / Squad**
4. Set the **Server URL** to:
   ```
   https://your-app.onrender.com/api/vapi/webhook
   ```
5. This tells Vapi to send an `assistant-request` event to your backend on every incoming call
6. Your backend will return the assistant ID with `caller_memory` as a dynamic variable

> **Important**: Replace `your-app.onrender.com` with your actual Render URL.

---

## Step 3: Add `{{caller_memory}}` to the Assistant Prompt

1. Go to **Vapi Dashboard → Assistants → Saarthi**
2. In the **System Prompt** (First Message or Instructions), add this variable and guidance:

```
{{caller_memory}}

IMPORTANT INSTRUCTIONS FOR USING CALLER CONTEXT:
- Use previous context only when it is directly relevant to the current conversation.
- Do not mention previous calls unless it is useful to the caller.
- Do not pretend to remember something that is not present in the context.
- Treat the caller's current message as the primary source of truth.
- If previous context conflicts with the caller's current statement, trust the current statement.
- Be natural. Do not read out the context verbatim.
```

3. Place `{{caller_memory}}` near the beginning of the system prompt, before the main instructions.

---

## Step 4: Create the `generate_action_plan` Custom Tool

This enables **Feature 2: Real-Time Action Plan Generation**.

1. Go to **Vapi Dashboard → Assistants → Saarthi**
2. Scroll to **Tools** section
3. Click **Add Tool → Function**
4. Configure:

**Function Name:**
```
generate_action_plan
```

**Description:**
```
Generate a concise, practical, step-by-step action plan after enough information about the caller's situation has been collected. Only call this tool when you have sufficient context about the problem, the caller's goal, and the urgency level. Do NOT call this immediately at the start of the conversation.
```

**Parameters Schema (JSON):**
```json
{
  "type": "object",
  "properties": {
    "problem": {
      "type": "string",
      "description": "A clear description of the caller's main problem or situation"
    },
    "relevant_context": {
      "type": "string",
      "description": "Important context about the situation including family details, documents involved, deadlines, etc."
    },
    "caller_goal": {
      "type": "string",
      "description": "What the caller wants to achieve or needs help with"
    },
    "urgency": {
      "type": "string",
      "enum": ["low", "medium", "high", "critical"],
      "description": "How urgent the caller's situation is"
    }
  },
  "required": ["problem", "relevant_context", "caller_goal", "urgency"]
}
```

**Server URL:**
```
https://your-app.onrender.com/api/vapi/webhook
```

5. Save the tool configuration.

---

## Step 5: Add Tool Usage Instructions to the Prompt

Add the following to the Saarthi assistant's system prompt:

```
TOOL USAGE - generate_action_plan:
- Do NOT call generate_action_plan immediately at the start of the call.
- First understand the caller's problem fully.
- Ask relevant follow-up questions when necessary (e.g., what documents they have, deadlines, family situation).
- Only call the tool after you have collected enough information.
- When you receive the action plan result, explain it to the caller naturally — do not read raw data.
- Present the steps in a conversational, helpful manner.
- If professional help is recommended, gently suggest it.
```

---

## Step 6: Configure Server Webhook for Transcript Events

This enables **Feature 3: Real-Time Risk Detection**.

1. Go to **Vapi Dashboard → Assistants → Saarthi**
2. Scroll to **Server URL** (or **Advanced → Server URL**)
3. Set the Server URL to:
   ```
   https://your-app.onrender.com/api/vapi/webhook
   ```
4. Under **Server Events**, ensure these are enabled:
   - ✅ `transcript`
   - ✅ `status-update`
   - ✅ `end-of-call-report`
   - ✅ `conversation-update`
   - ✅ `tool-calls`

> This ensures the backend receives real-time transcript updates for risk detection, tool calls for action plan generation, and end-of-call reports for final analysis.

---

## Step 7: Verify Configuration

### Check Environment Variables

Your deployment should have these environment variables:

| Variable | Value |
|---|---|
| `VAPI_API_KEY` | Your Vapi API key |
| `VAPI_ASSISTANT_ID` | Your Saarthi assistant ID |
| `GEMINI_API_KEY` | Your Google Gemini API key |
| `DATABASE_URL` | Your PostgreSQL connection string |

### Verify Webhook Connectivity

1. Open your dashboard at `https://your-app.onrender.com`
2. Make a test call to the Saarthi phone number
3. Check the Render logs for:
   ```
   Vapi webhook received: type=assistant-request
   Returning assistant xxxx with caller context
   ```
4. If you see these logs, the assistant selector is working.

---

## Local Testing

When testing locally:

1. Use a tunnel service (ngrok, localtunnel) to expose your local server:
   ```bash
   ngrok http 8000
   ```
2. Replace all `https://your-app.onrender.com` URLs with your tunnel URL:
   ```
   https://abc123.ngrok.io/api/vapi/webhook
   ```
3. Update the Vapi dashboard with the tunnel URL for both:
   - Phone number Server URL
   - Assistant Server URL
4. Remember to switch back to the production URL when done testing.

---

## Summary of All Vapi Changes

| Setting | Location | Value |
|---|---|---|
| Phone Number → Server URL | Phone Numbers | `{BACKEND_URL}/api/vapi/webhook` |
| Assistant System Prompt | Assistants → Saarthi | Add `{{caller_memory}}` + instructions |
| Custom Tool | Assistants → Saarthi → Tools | `generate_action_plan` function |
| Tool Server URL | Tool configuration | `{BACKEND_URL}/api/vapi/webhook` |
| Assistant Server URL | Assistants → Saarthi → Advanced | `{BACKEND_URL}/api/vapi/webhook` |
| Server Events | Assistants → Saarthi → Advanced | transcript, tool-calls, status-update, end-of-call-report, conversation-update |
