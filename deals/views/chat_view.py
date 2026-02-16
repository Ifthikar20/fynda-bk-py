"""
Chat View

AI-powered conversational shopping assistant.
Uses OpenAI GPT-4o-mini to understand natural language queries
and generate conversational responses alongside product results.
"""

import os
import json
import logging

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status

logger = logging.getLogger(__name__)


def _get_openai_client():
    """Lazy-load OpenAI client."""
    try:
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return None
        return OpenAI(api_key=api_key)
    except ImportError:
        logger.warning("openai package not installed")
        return None


def _search_products(query, limit=20):
    """Search for products using the existing orchestrator (same as /api/search/)."""
    try:
        from deals.services import orchestrator
        result = orchestrator.search(query)
        deals = result.to_dict().get("deals", [])[:limit]
        return deals
    except Exception as e:
        logger.error(f"Product search failed: {e}")
        return []


# OpenAI function-calling schema for the chat assistant
CHAT_FUNCTION_SCHEMA = {
    "name": "search_products",
    "description": "Search for fashion products based on the user's request. Extract the best search query from their message.",
    "parameters": {
        "type": "object",
        "properties": {
            "search_query": {
                "type": "string",
                "description": "A concise product search query for Amazon (e.g. 'brown sneakers white sole men'). Strip conversational filler and keep only product-relevant keywords.",
            },
            "response": {
                "type": "string",
                "description": "A short, friendly 1-2 sentence response to the user. Do NOT list products — just acknowledge their request and add any helpful shopping tips. Keep it under 40 words.",
            },
        },
        "required": ["search_query", "response"],
    },
}

SYSTEM_PROMPT = """You are Fynda, a friendly AI fashion shopping assistant. Your job:
1. Understand what the user is looking for (product type, color, style, budget, brand).
2. Extract a concise search query to find matching products.
3. Write a short, helpful response (1-2 sentences, under 40 words). Be warm but concise.

Rules:
- Never list products yourself — products are shown separately.
- If the user asks about brands, mention 2-3 popular ones for that category.
- If the query is vague, still extract the best search query you can.
- Do not use emojis.
"""


class ChatView(APIView):
    """
    AI chat shopping assistant.

    POST /api/chat/

    Request body:
        message  - User's message (required)
        history  - Previous messages [{ role, text }] (optional, max 10)

    Response:
        response  - AI's conversational response
        products  - List of matching products
        search_query - The extracted search query
    """
    permission_classes = [AllowAny]

    def post(self, request):
        message = (request.data.get("message") or "").strip()
        history = request.data.get("history") or []

        if not message:
            return Response(
                {"error": "message is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(message) > 500:
            message = message[:500]

        # Build conversation for OpenAI
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Add recent history (last 10 messages max)
        for msg in history[-10:]:
            role = msg.get("role", "user")
            text = msg.get("text", "")
            if role in ("user", "assistant") and text:
                messages.append({"role": role, "content": text})

        messages.append({"role": "user", "content": message})

        # Call OpenAI
        client = _get_openai_client()
        if not client:
            # Fallback: use message as search query directly
            products = _search_products(message)
            return Response({
                "response": f"Here's what I found for \"{message}\".",
                "products": products,
                "search_query": message,
            })

        try:
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=[{
                    "type": "function",
                    "function": CHAT_FUNCTION_SCHEMA,
                }],
                tool_choice={
                    "type": "function",
                    "function": {"name": "search_products"},
                },
                temperature=0.7,
                max_tokens=200,
            )

            tool_call = completion.choices[0].message.tool_calls[0]
            args = json.loads(tool_call.function.arguments)
            search_query = args.get("search_query", message)
            ai_response = args.get("response", f"Let me find that for you.")

        except Exception as e:
            logger.error(f"OpenAI chat failed: {e}")
            search_query = message
            ai_response = f"Here's what I found for \"{message}\"."

        # Search Amazon with extracted query
        products = _search_products(search_query)

        return Response({
            "response": ai_response,
            "products": products,
            "search_query": search_query,
        })
