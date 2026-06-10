"""
concierge.py
AI orchestration layer for the Automation Arsenal.
Routes natural language requests to the appropriate automation engine
and synthesizes human-readable responses with recommended actions.

IMPORTANT: This agent never makes autonomous decisions that modify data.
It always returns a recommendation and requires explicit user confirmation
for any destructive action.

Author: Your Name
License: MIT
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
from openai import OpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Intent(Enum):
    """Classified user intents mapped to automation engines."""
    CHECK_SERVICE_HEALTH = "check_service_health"
    ANALYZE_LAB_RESULTS = "analyze_lab_results"
    RECONCILE_PATIENTS = "reconcile_patients"
    PROCESS_INVOICES = "process_invoices"
    ORGANIZE_FILES = "organize_files"
    FIND_DUPLICATES = "find_duplicates"
    GENERAL_QUESTION = "general_question"


@dataclass
class RoutedRequest:
    """A user request that has been classified and routed."""
    original_text: str
    intent: Intent
    confidence: float
    parameters: Dict[str, Any]
    safety_flags: List[str]
    requires_confirmation: bool


class IntentRouter:
    """
    Routes natural language to the correct automation engine.
    
    Uses keyword matching and lightweight pattern recognition
    as a deterministic first pass. In production, this would
    call an LLM API with tool-use capability (OpenAI function
    calling, Anthropic tool use, or local model).
    """

    # Keyword patterns for intent classification
    INTENT_PATTERNS = {
        Intent.CHECK_SERVICE_HEALTH: [
            "health", "monitor", "check", "status", "slow", "down",
            "response time", "latency", "ssl", "certificate", "endpoint",
            "api", "service", "auth", "dashboard"
        ],
        Intent.ANALYZE_LAB_RESULTS: [
            "lab", "result", "blood", "test", "potassium", "glucose",
            "creatinine", "hemoglobin", "patient", "abnormal", "critical",
            "clinical", "reference range"
        ],
        Intent.RECONCILE_PATIENTS: [
            "reconcile", "patient", "demographic", "ehr", "record",
            "match", "duplicate patient", "merge"
        ],
        Intent.PROCESS_INVOICES: [
            "invoice", "bill", "payment", "pdf", "extract", "accounting",
            "vendor", "line item", "tax", "subtotal"
        ],
        Intent.ORGANIZE_FILES: [
            "organize", "folder", "directory", "clean", "sort",
            "categorize", "arrange"
        ],
        Intent.FIND_DUPLICATES: [
            "duplicate", "dedup", "same file", "copy", "identical",
            "redundant", "space", "cleanup"
        ],
    }

    def classify(self, text: str) -> RoutedRequest:
        """
        Classify user intent from natural language.
        
        Args:
            text: User's natural language request
            
        Returns:
            RoutedRequest with classified intent and extracted parameters
        """
        text_lower = text.lower()
        scores = {}

        for intent, keywords in self.INTENT_PATTERNS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[intent] = score

        if not scores:
            return RoutedRequest(
                original_text=text,
                intent=Intent.GENERAL_QUESTION,
                confidence=0.0,
                parameters={},
                safety_flags=["unclassified_intent"],
                requires_confirmation=False
            )

        # Select highest-scoring intent
        best_intent = max(scores, key=scores.get)
        max_score = scores[best_intent]
        total_possible = len(self.INTENT_PATTERNS[best_intent])
        confidence = min(max_score / max(total_possible * 0.3, 1), 1.0)

        # Extract parameters from text
        parameters = self._extract_parameters(text, best_intent)

        # Determine safety requirements
        safety_flags = self._safety_check(best_intent, parameters)

        return RoutedRequest(
            original_text=text,
            intent=best_intent,
            confidence=round(confidence, 2),
            parameters=parameters,
            safety_flags=safety_flags,
            requires_confirmation=len(safety_flags) > 0
        )

    def _extract_parameters(self, text: str, intent: Intent) -> Dict[str, Any]:
        """Extract relevant parameters from the request text."""
        params = {}

        # Extract time references
        if "today" in text.lower():
            params["time_range"] = "today"
        elif "week" in text.lower():
            params["time_range"] = "week"
        elif "month" in text.lower():
            params["time_range"] = "month"
        else:
            params["time_range"] = "latest"

        # Extract specific endpoints if mentioned
        if intent == Intent.CHECK_SERVICE_HEALTH:
            words = text.lower().split()
            known_endpoints = ["auth", "api", "dashboard", "payment", "login"]
            params["endpoints"] = [ep for ep in known_endpoints if ep in words]

        # Extract patient context
        if intent in [Intent.ANALYZE_LAB_RESULTS, Intent.RECONCILE_PATIENTS]:
            params["review_required"] = "critical" in text.lower()

        return params

    def _safety_check(self, intent: Intent, parameters: Dict) -> List[str]:
        """
        Safety validation layer.
        Returns list of safety flags. Empty list = safe to proceed.
        """
        flags = []

        # Any healthcare request requires confirmation
        if intent in [Intent.ANALYZE_LAB_RESULTS, Intent.RECONCILE_PATIENTS]:
            flags.append("healthcare_data_access")
            flags.append("phi_handling_required")

        # File system modifications require confirmation
        if intent in [Intent.ORGANIZE_FILES, Intent.FIND_DUPLICATES]:
            flags.append("filesystem_modification")

        return flags


class ResponseSynthesizer:
    """
    Synthesizes human-readable responses from automation engine output.
    
    In production, this would use an LLM to generate natural language
    summaries. Here we use structured templates that demonstrate
    the pattern.
    """

    def synthesize(self, request: RoutedRequest, engine_output: Any) -> str:
        """Generate a natural language response from engine output."""
        
        if request.intent == Intent.CHECK_SERVICE_HEALTH:
            return self._synthesize_health_response(engine_output)
        elif request.intent == Intent.ANALYZE_LAB_RESULTS:
            return self._synthesize_lab_response(engine_output, request)
        elif request.intent == Intent.PROCESS_INVOICES:
            return self._synthesize_invoice_response(engine_output)
        elif request.intent == Intent.GENERAL_QUESTION:
            return self._synthesize_general_response(request)
        else:
            return self._synthesize_default_response(request, engine_output)

    def _synthesize_health_response(self, output: Dict) -> str:
        """Synthesize service health check results."""
        if not output:
            return "I checked the services but received no data. The monitoring system may be offline."

        healthy = [s for s in output if s.get("is_healthy")]
        unhealthy = [s for s in output if not s.get("is_healthy")]

        lines = []
        lines.append(f"Health check complete: {len(healthy)} services healthy, {len(unhealthy)} need attention.\n")

        if unhealthy:
            lines.append("⚠️ Services requiring attention:")
            for service in unhealthy:
                lines.append(f"  • {service['url']}: {service.get('error_message', 'Check failed')}")

        if healthy:
            avg_response = sum(s.get("response_time_ms", 0) for s in healthy) / len(healthy)
            lines.append(f"\nAverage response time across healthy services: {avg_response:.0f}ms")

        return "\n".join(lines)

    def _synthesize_lab_response(self, output: Dict, request: RoutedRequest) -> str:
        """Synthesize lab analysis results with clinical context."""
        if not output or output.get("status") == "no_data":
            return "No lab results found for the specified criteria."

        critical = output.get("critical_findings", [])
        lines = []
        lines.append(f"Lab analysis complete. Analyzed {output.get('total_tests_analyzed', 0)} tests.\n")

        if critical:
            lines.append("🔴 CRITICAL FINDINGS REQUIRING IMMEDIATE ATTENTION:")
            for finding in critical:
                lines.append(f"\n  Test: {finding['test']}")
                lines.append(f"  Value: {finding['value']}")
                lines.append(f"  Severity: {finding['severity'].upper()}")
                lines.append(f"  Recommended Action: {finding['action']}")
        else:
            lines.append("✅ No critical findings detected.")

        # Add disclaimer
        lines.append("\n---")
        lines.append("⚠️ This is an automated analysis for demonstration purposes.")
        lines.append("All findings must be reviewed by a qualified clinician before any action is taken.")

        return "\n".join(lines)

    def _synthesize_invoice_response(self, output: Dict) -> str:
        """Synthesize invoice processing results."""
        if not output or output.get("total_invoices", 0) == 0:
            return (
                "I can process invoices, but I need a specific file path.\n\n"
                "Example: 'Extract data from sample_data/invoice.pdf'\n"
                "I'll extract invoice number, vendor, line items, and validate totals."
            )

        lines = []
        lines.append(f"Processed {output.get('total_invoices', 0)} invoices.\n")
        lines.append(f"  Total value: ${output.get('total_value', 0):,.2f}")
        lines.append(f"  Validation failures: {output.get('validation_failures', 0)}")
        return "\n".join(lines)

    def _synthesize_general_response(self, request: RoutedRequest) -> str:
        """Handle requests that don't map to a specific engine."""
        return (
            "I can help with several automation tasks:\n\n"
            "• Check service health — 'Is the auth API slow today?'\n"
            "• Analyze lab results — 'Any critical potassium levels this week?'\n"
            "• Process invoices — 'Extract data from invoice INV-2026-0042'\n"
            "• Find duplicates — 'How many duplicate files are in Downloads?'\n"
            "• Organize files — 'Organize my Desktop folder by type'\n\n"
            "What would you like me to do?"
        )

    def _synthesize_default_response(self, request: RoutedRequest, output: Any) -> str:
        """Fallback response template."""
        if isinstance(output, dict) and output.get("status") == "blocked":
            return (
                f"⚠️  This operation is blocked for safety.\n\n"
                f"Reason: {output.get('reason', 'Requires human authorization.')}\n"
                f"Safety flags: {', '.join(output.get('safety_flags', []))}\n\n"
                f"Please confirm you want to proceed, or run with --dry-run first."
            )
            
        return f"Task classified as '{request.intent.value}' (confidence: {request.confidence}).\nResult: {output}"


class AutomationConcierge:
    """
    Main AI orchestration agent.
    
    Coordinates intent classification, tool routing, safety validation,
    and response synthesis. Designed to be extended with actual LLM
    integration (OpenAI, Anthropic, or local models via Ollama).
    """

    def __init__(self):
        self.router = IntentRouter()
        self.synthesizer = ResponseSynthesizer()
        self.conversation_history: List[Dict] = []
        #client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    def process(self, user_input: str) -> str:
        """
        Process a natural language request end-to-end.
        
        Args:
            user_input: Natural language request from user
            
        Returns:
            Human-readable response with recommendations
        """
        # Step 1: Classify intent
        request = self.router.classify(user_input)
        logger.info(f"Classified: {request.intent.value} (confidence: {request.confidence})")

        # Step 2: Safety check
        if request.requires_confirmation:
            logger.warning(f"Safety flags: {request.safety_flags}")

        # Step 3: Route to appropriate engine (simulated here)
        # In production: call the actual project module
        engine_output = self._call_engine(request)

        # Step 4: Synthesize response
        # If engine_output is a string (from LLM), return it directly
        if isinstance(engine_output, str):
            response = engine_output
        else:
            response = self.synthesizer.synthesize(request, engine_output)

        # Step 5: Log to conversation history
        self.conversation_history.append({
            "user_input": user_input,
            "intent": request.intent.value,
            "confidence": request.confidence,
            "safety_flags": request.safety_flags,
            "timestamp": __import__('datetime').datetime.now().isoformat()
        })

        return response

    def _call_engine(self, request: RoutedRequest) -> Any:
        """Call engine. Uses Groq LLM if API key available, else simulated."""
        if os.environ.get("GROQ_API_KEY"):
            return self._call_engine_with_llm(request)
        else:
            # Fallback to simulated output for demo mode
            return self._simulated_engine_output(request)
        
    def execute_tool(self, tool_name: str, parameters: Dict) -> Any:
        """
        Execute a tool from the automation arsenal.
        Returns real output from the corresponding engine.
        """
        import sys
        from pathlib import Path

        # Add project paths so we can import engines
        projects_root = Path(__file__).parent.parent

        if tool_name == "check_service_health":
            # Import WatchTower and run health check
            watchtower_path = projects_root / "watchtower"
            if str(watchtower_path) not in sys.path:
                sys.path.insert(0, str(watchtower_path))

            try:
                from monitor import HealthMonitor, EndpointConfig
                import asyncio

                endpoints = [
                    EndpointConfig(
                        url="https://jsonplaceholder.typicode.com/posts/1",
                        expected_status=200,
                        timeout_seconds=10
                    ),
                    EndpointConfig(
                        url="https://jsonplaceholder.typicode.com/posts/99999",
                        expected_status=200,
                        timeout_seconds=10
                    ),
                ]

                monitor = HealthMonitor(endpoints)
                results = asyncio.run(monitor.run_check())

                # Format results for the LLM
                formatted = []
                for r in results:
                    formatted.append({
                        "url": r.url,
                        "status_code": r.status_code,
                        "response_time_ms": r.response_time_ms,
                        "is_healthy": r.is_healthy,
                        "error": r.error_message
                    })
                return formatted

            except Exception as e:
                return {"error": f"Failed to run health check: {str(e)}"}

        if tool_name == "analyze_lab_results":
            # Return simulated clinical analysis (MedRecon integration)
            return {
                "tests_analyzed": 3,
                "critical_findings": [
                    {
                        "test": "POTASSIUM",
                        "value": 6.2,
                        "unit": "mmol/L",
                        "reference": "3.5-5.1",
                        "severity": "CRITICAL",
                        "action": "Immediate ECG and cardiac monitoring required."
                    }
                ],
                "disclaimer": "All findings require clinical review before action."
            }

        if tool_name == "find_duplicates":
            return {
                "status": "requires_path",
                "message": "Please specify the directory to scan for duplicates."
            }

        if tool_name == "process_invoices":
            return {
                "status": "requires_path",
                "message": "Please specify the invoice PDF file path."
            }

        return {"message": f"Tool '{tool_name}' executed successfully."}    

    def save_history(self, filepath: str = "conversation_history.json"):
        """Persist conversation history to JSON file."""
        import json
        with open(filepath, 'w') as f:
            json.dump(self.conversation_history, f, indent=2, default=str)


    def _call_engine_with_llm(self, request: RoutedRequest) -> Any:
        """Route using Groq LLM with native tool calling."""
        import os
        import json
        from groq import Groq

        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            return "GROQ_API_KEY not set. Run: $env:GROQ_API_KEY = 'your_key'"

        client = Groq(api_key=api_key)

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "check_service_health",
                    "description": "Check health and response times of API endpoints",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "service_name": {
                                "type": "string",
                                "description": "The service to check (e.g., auth, api, dashboard)"
                            }
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
                            "test_name": {
                                "type": "string",
                                "description": "Specific lab test to analyze (e.g., potassium, glucose)"
                            },
                            "time_range": {
                                "type": "string",
                                "enum": ["today", "week", "month"],
                                "description": "Time range for results"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "find_duplicates",
                    "description": "Find duplicate files in a directory",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "directory": {
                                "type": "string",
                                "description": "Directory path to scan"
                            }
                        },
                        "required": ["directory"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "process_invoices",
                    "description": "Extract data from PDF invoices",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path to the invoice PDF file"
                            }
                        },
                        "required": ["file_path"]
                    }
                }
            }
        ]

        system_prompt = """You are an automation concierge with access to real tools.
When a user asks you to check something, use the appropriate tool.
After getting tool results, summarize them in plain English.
If a request involves deleting or modifying data without review, REFUSE.
Always prioritize safety over speed."""

        try:
            # First call: Let the model decide if it needs tools
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": request.original_text}
                ],
                tools=tools,
                tool_choice="auto",
                temperature=0.3,
                max_tokens=500
            )

            message = response.choices[0].message

            # If the model wants to call a tool
            if message.tool_calls:
                tool_call = message.tool_calls[0]
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                logger.info(f"Executing tool: {tool_name} with args: {tool_args}")

                # Execute the actual tool
                tool_result = self.execute_tool(tool_name, tool_args)

                # Second call: Let the model summarize the tool output
                summary_response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": request.original_text},
                        {"role": "assistant", "content": f"I'll check that using the {tool_name} tool."},
                        {"role": "user", "content": f"Tool result: {json.dumps(tool_result, default=str)}. Please summarize these results in plain English."}
                    ],
                    temperature=0.3,
                    max_tokens=500
                )

                return summary_response.choices[0].message.content

            # If no tool needed, return the direct response
            return message.content

        except Exception as e:
            return f"Error: {str(e)}. Please try again."
    
    def _simulated_engine_output(self, request: RoutedRequest) -> Any:
        """Return simulated output when no LLM is available."""
        if request.intent == Intent.CHECK_SERVICE_HEALTH:
            return [
                {
                    "url": "https://api.example.com/health",
                    "is_healthy": True,
                    "status_code": 200,
                    "response_time_ms": 142,
                    "error_message": None
                },
                {
                    "url": "https://auth.example.com/token",
                    "is_healthy": False,
                    "status_code": None,
                    "response_time_ms": 0,
                    "error_message": "Timeout after 10s"
                }
            ]

        if request.intent == Intent.ANALYZE_LAB_RESULTS:
            return {
                "status": "success",
                "total_tests_analyzed": 5,
                "critical_findings": [
                    {
                        "test": "POTASSIUM",
                        "value": 6.2,
                        "severity": "critical",
                        "action": "URGENT: Immediate ECG and cardiac monitoring."
                    }
                ]
            }

        if request.intent == Intent.RECONCILE_PATIENTS:
            return {
                "status": "blocked",
                "reason": "Patient record merging requires explicit human authorization.",
                "safety_flags": request.safety_flags
            }
        
        if request.intent == Intent.FIND_DUPLICATES:
            return {
                "status": "blocked",
                "reason": "Automatic file deletion is disabled. Run in dry-run mode first.",
                "safety_flags": request.safety_flags
            }
        
        if request.intent == Intent.PROCESS_INVOICES:
            return {
                "total_invoices": 0,
                "total_value": 0,
                "validation_failures": 0
            }

        return {"message": "This request requires additional clarification or human approval."}

# ─── Demonstration ────────────────────────────────────────────

if __name__ == "__main__":
    concierge = AutomationConcierge()

    print("=" * 60)
    print("AUTOMATION ARSENAL — AI CONCIERGE DEMO")
    print("=" * 60)
    print("Type your request or 'quit' to exit.\n")

    # Demo requests
    demo_requests = [
        "Is the auth API slow this week?",
        "Any critical lab results from today?",
        "What can you help me with?",
        "Process the invoice on my desktop",
    ]

    for req in demo_requests:
        print(f"👤 User: {req}")
        response = concierge.process(req)
        print(f"🤖 Concierge: {response}\n")
        print("-" * 40 + "\n")

    # Interactive mode
    while True:
        try:
            user_input = input("👤 You: ").strip()
            if user_input.lower() in ["quit", "exit", "q"]:
                print("Shutting down. Conversation history saved to memory.")
                break
            if not user_input:
                continue

            response = concierge.process(user_input)
            print(f"\n🤖 Concierge: {response}\n")

        except KeyboardInterrupt:
            print("\nShutting down.")
            break