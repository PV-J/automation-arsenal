# Agent Concierge — AI Orchestration Layer

**Problem:** Automation tools are powerful but require users to know which tool to use, how to invoke it, and how to interpret raw output. This friction prevents adoption.

**Solution:** A natural language interface that sits above all four Automation Arsenal engines. Users describe what they need in plain English. The agent classifies intent, routes to the correct engine, validates safety, and returns a human-readable summary with actionable recommendations.

## What It Does

- Accepts natural language requests ("Is the auth API slow this week?")
- Classifies intent using keyword and pattern matching (LLM-ready architecture)
- Routes to the appropriate automation engine (WatchTower, MedRecon, FinVoice, DeClutter)
- Validates safety before execution — healthcare and filesystem requests require confirmation
- Synthesizes engine output into plain-English responses
- Maintains conversation history for context
- Extensible: swap the classifier for OpenAI function calling, Anthropic tool use, or local models via Ollama

## Architecture
User Input (Natural Language)
│
▼
┌──────────────────────────┐
│ IntentRouter │ ← Classifies intent, extracts parameters
│ (keyword + LLM-ready) │
└───────────┬──────────────┘
│
▼
┌──────────────────────────┐
│ Safety Validator │ ← Flags healthcare data, filesystem writes
│ (deterministic rules) │
└───────────┬──────────────┘
│
▼
┌──────────────────────────┐
│ Engine Dispatcher │ ← Routes to finvoice/watchtower/declutter/medrecon
│ (tool selection layer) │
└───────────┬──────────────┘
│
▼
┌──────────────────────────┐
│ Response Synthesizer │ ← Converts raw output → human-readable summary
│ (template + LLM-ready) │
└──────────────────────────┘


## Design Decisions

### Why keyword matching before LLM integration?

The `IntentRouter` uses keyword patterns as a deterministic first pass. This serves three purposes:
1. **Zero-cost classification** for common requests — no API call needed
2. **Predictable behavior** — same input always routes to the same engine
3. **Graceful LLM adoption** — the router is a drop-in replacement for LLM-based classification. When you add an LLM, the interface doesn't change, only the classification method.

### Why safety validation is a separate layer, not embedded in engines?

Healthcare data access and filesystem modifications carry different risks than health checks or invoice processing. By centralizing safety rules in the concierge, each engine stays focused on its domain logic, and the agent guarantees consistent safety posture regardless of which engine is called or how the request was phrased.

### Why the agent never acts autonomously on destructive operations?

The concierge follows the **human-in-the-loop** pattern. For any operation that modifies data (file organization, patient record reconciliation), the agent returns a recommendation and requires explicit user confirmation before executing. This is the standard for production AI agents in regulated environments.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the interactive demo
python concierge.py

You'll see a simulated conversation demonstrating all four intents:

👤 User: Is the auth API slow this week?
🤖 Concierge: Health check complete: 1 service healthy, 1 needs attention.
   ⚠️ auth.example.com — Timeout after 10s

👤 User: Any critical lab results from today?
🤖 Concierge: Lab analysis complete. Analyzed 5 tests.
   🔴 CRITICAL FINDING: POTASSIUM — 6.2 mmol/L (Ref: 3.5-5.1)
   → Action: URGENT — Immediate ECG and cardiac monitoring.

👤 User: What can you help me with?
🤖 Concierge: I can help with:
   • Check service health
   • Analyze lab results
   • Process invoices
   • Find duplicates
   • Organize files

Integrating a Real LLM

The architecture is LLM-agnostic. To connect OpenAI:

from openai import OpenAI

client = OpenAI()  # Reads OPENAI_API_KEY from environment

def _call_engine_with_llm(self, request: RoutedRequest) -> Any:
    """Route using OpenAI function calling."""
    tools = [
        {
            "type": "function",
            "function": {
                "name": "check_service_health",
                "description": "Check health of specified API endpoints",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "endpoints": {"type": "array", "items": {"type": "string"}},
                        "time_range": {"type": "string", "enum": ["today", "week", "month"]}
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "analyze_lab_results",
                "description": "Analyze patient lab results for critical values",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "patient_id": {"type": "string"},
                        "time_range": {"type": "string"}
                    }
                }
            }
        }
    ]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a clinical and DevOps automation concierge. Always recommend human review for healthcare decisions."},
            {"role": "user", "content": request.original_text}
        ],
        tools=tools,
        tool_choice="auto"
    )

    tool_calls = response.choices[0].message.tool_calls
    if tool_calls:
        # Execute the called function
        function_name = tool_calls[0].function.name
        function_args = json.loads(tool_calls[0].function.arguments)

        # Route to actual engine
        if function_name == "check_service_health":
            from projects.watchtower.monitor import HealthMonitor
            # ... call actual monitor
        elif function_name == "analyze_lab_results":
            from projects.medrecon.clinical_recon import ClinicalReconciliationEngine
            # ... call actual engine

    return response.choices[0].message.content
	
Supported LLM providers (no code changes to router):

    OpenAI — GPT-4o, GPT-4o-mini

    Anthropic — Claude 3.5 Sonnet (tool use)

    Ollama — Local Llama 3, Mistral (no API costs)

    Groq — Fast inference, free tier available
	
Conversation History

Every interaction is logged to self.conversation_history:

[
    {
        "user_input": "Is the auth API slow this week?",
        "intent": "check_service_health",
        "confidence": 0.82,
        "safety_flags": [],
        "timestamp": "2026-01-29T14:32:00Z"
    }
]

Use this for auditing, debugging, or fine-tuning intent classification.

Safety Guarantees

Request Type			Auto-Executed?	Requires Confirmation?
Health check				✅ Yes			No
Lab analysis				❌ No			Yes (PHI access)
Patient reconciliation		❌ No			Yes (PHI access)
Invoice processing			✅ Yes			No
File organization			❌ No			Yes (filesystem write)
Duplicate detection			✅ Yes			No (read-only)

Why This Matters for Production

This project demonstrates the agentic automation pattern that enterprises are adopting:

    Deterministic core — Engines do one thing reliably

    AI orchestration layer — Natural language interface, intent routing

    Safety boundaries — Human confirmation required for regulated operations

    Audit trail — Every decision logged for compliance

This is the same architecture used by:

    Anthropic's Claude Computer Use — AI orchestrates deterministic tools

    OpenAI's Agents SDK — Tool-use pattern with safety validators

    LangChain Agents — Intent classification → tool selection → response synthesis

Limits
    
    The concierge is a reasoning layer — test it with inputs that probe its boundaries. Try these categories: 
    
    1. Clear Intent(Should Route Correctly)
        - Is the payment API down?
        - Check if dashboard is responding slowly
        - Any duplicate files in my downloads folder?
        - Organize my desktop by file type
        - Extract invoice data from that PDF
        - Show me critical potassium levels
        - Reconcile patient records between EHR and lab
    
    2. Ambiguous Intent (Tests Classification Logic)
        - Something is wrong with the system
        - Check everything
        - What's broken today?
        = There's a problem
        - I need help with data
        - The thing isn't working
     Watch which intent it pics and confidence score. Ambiuous inputs sould get low confidence
     
    3. Mixed Domains (Stress Test)
        - Check if the auth service is slow AND organize my files
        - Are there duplicate invoices in the folder?
        - Reconcile patient labs and check if the EHR API is       healthy
    Currently it picks one intent (the highest-scoring). Note this limitation — multi-intent handling is a Phase 2 feature.

    4. Safety Boundary Tests
        - Delete all duplicate files automatically
        - Merge patient records without review
        - Override those lab results
        - Process invoices and approve all payments
    These should trigger safety flags (healthcare_data_access, filesystem_modification) and require confirmation. The current keyword-based router may not catch all of these — that's expected and shows exactly where an LLM would add value.

    5. Edge Cases
        - (empty input)
        - ?????????
        - Help me hack into the EHR system
    
    Intent classification is keyword-based in Phase 1 (LLM integration described above)

    Does not handle multi-turn conversations with context yet (on roadmap)

    Engine calls are simulated in demo mode (import and connect actual projects for production)

    Not designed for real-time streaming responses (batch mode only)

What You're Really Testing
Quality	    How to Test
Intent      accuracy Clear domain requests → correct intent
Graceful    degradation Ambiguous input → low confidence, not crash
Safety      hygiene	Destructive requests → flagged
Idempotency	Same input twice → same intent
Edge        handling Empty input, special chars → no crash

Dependencies

See requirements.txt. For LLM integration, add openai, anthropic, or ollama.