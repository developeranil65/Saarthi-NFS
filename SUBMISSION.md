# Saarthi - Hackathon Submission

## 1. Project Overview: What we built and how it works

**Saarthi** is an AI-powered voice guidance platform designed specifically for non-technical users in India who may not know how to use text-based AI tools like ChatGPT. 

Instead of downloading an app or typing complex prompts, users simply dial a toll-free phone number and speak naturally in **Hindi, Hinglish, or English**. Saarthi understands their problem and provides actionable, step-by-step guidance on critical topics like government schemes, legal matters, medical emergencies, and financial literacy.

### How it Works:
1. **The Call:** The user calls a real phone number (+1 380-227-9014).
2. **Voice AI (Vapi):** The call is handled by an advanced AI Voice Assistant (powered by Vapi) that communicates naturally with the user, understanding context and language nuances.
3. **Backend Intelligence (FastAPI + Gemini):** As the call progresses, our backend receives real-time webhooks (transcripts and events) and processes them.
4. **Operations Dashboard:** A centralized, web-based dashboard allows administrators to monitor active calls in real-time, view full transcripts, track risk levels, and review AI-generated action plans.

## 2. Key Features

- **Multilingual Voice Interface:** Supports seamless communication in Hindi, Hinglish, and English without any user configuration.
- **Smart Caller Memory:** The system remembers past interactions. If a user calls back, the AI is injected with context from their previous calls, allowing for continuous support without forcing the user to repeat themselves.
- **Real-Time Action Plan Generation:** While the call is active, the system analyzes the conversation using Google Gemini and generates a structured, prioritized 1-6 step action plan to help the user resolve their specific issue (e.g., gathering documents, visiting a local office).
- **Intelligent Risk Detection:** A real-time engine scans transcripts for high-risk indicators (suicide, self-harm, medical emergencies, violence) and medium-risk indicators (financial fraud, legal threats). High-risk calls are immediately flagged with a pulsing red alert on the live dashboard.
- **Live Operations Dashboard:** A responsive, single-page application (SPA) featuring an "Executive Emerald" premium theme. It provides real-time metrics, search/filtering, and detailed call records.

## 3. Technical Decisions & Architecture

- **Backend Framework:** We chose **FastAPI** (Python 3.12+) because of its native support for asynchronous programming, which is critical for handling real-time, concurrent webhooks from the voice AI provider without blocking.
- **Database:** **PostgreSQL** with `asyncpg`. A relational database was chosen to maintain strong data integrity between users, calls, and conversation transcripts.
- **Voice Infrastructure:** We integrated **Vapi** to handle the complex telephony, speech-to-text, and text-to-speech pipelines, allowing us to focus on the intelligence layer.
- **LLM Integration:** **Google Gemini** was selected for transcript analysis and action plan generation due to its speed, high context window, and strong multilingual capabilities (especially for Hinglish/Hindi context).
- **Frontend:** To keep the deployment lightweight and fast, the dashboard is built with **Vanilla HTML/CSS/JS** as a Single Page Application (SPA), avoiding the overhead of heavy frameworks like React while still providing a premium, dynamic user experience.

## 4. Challenges Faced & How We Overcame Them

- **Handling Real-Time Asynchronous Events:** Vapi sends multiple webhooks simultaneously (status updates, transcripts, tool calls).
  - *Solution:* We implemented robust asynchronous handlers in FastAPI and used database-level locking and upserts to prevent race conditions (e.g., preventing duplicate user or call creation when `call-started` and `transcript` webhooks arrive at the exact same millisecond).
- **Dynamic Context Injection:** We needed the AI to remember users without sending massive, entire chat histories that would inflate latency and costs.
  - *Solution:* We built a `caller_memory` service that pulls only the 5 most recent completed calls, extracts the summaries and pending action items, and injects a highly compact text block into the Vapi assistant's prompt at the start of the call.
- **Reliable Action Plans during Live Calls:** Calling an LLM during a live voice conversation can cause awkward pauses if it takes too long.
  - *Solution:* We implemented a dual-layer approach. The AI first gathers context through conversation. When ready, it triggers a custom tool. The backend calls Gemini asynchronously. If Gemini takes too long or fails, the backend immediately falls back to a comprehensive, hardcoded rule-based system that returns a structured plan instantly.

## 5. Contribution and Work Done

*[PLACEHOLDER: Describe your specific contributions here. For example: "I developed the end-to-end architecture, integrated Vapi with the FastAPI backend, designed the PostgreSQL schema, and built the Vanilla JS operations dashboard."]*

## 6. Team Members & Roles

*[PLACEHOLDER: If you worked in a team, list the names and roles here. If you worked alone, state "Solo Developer: [Your Name] - Handled full-stack development, AI integration, and design."]*

---

## 7. Submission Links & Materials

- **GitHub Repository:** [https://github.com/developeranil65/Metx-NFS](https://github.com/developeranil65/Metx-NFS)
- **Live Dashboard Demo:** *[PLACEHOLDER: Insert your Render URL here, e.g., https://saarthi-backend.onrender.com]*
- **Demo Video:** *[PLACEHOLDER: Insert your Google Drive/YouTube link showing a live call and the dashboard updating]*
- **Phone Number to Test:** +1 (380) 227 9014

### Additional Documentation
- [README.md](./README.md) - Project setup and architecture overview.
- [VAPI_SETUP.md](./VAPI_SETUP.md) - Exact documentation on how the Voice AI was configured to communicate with our backend.
- [TESTING.md](./TESTING.md) - Detailed test scenarios to verify the intelligence features (Memory, Action Plans, Risk Detection).
