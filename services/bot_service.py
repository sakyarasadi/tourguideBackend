"""
Bot Service
===========
AI Chatbot Boilerplate - A proprietary asset of Exe.lk

Author: A B Geethan Imal
Organization: Exe.lk
Copyright (c) 2024 Exe.lk. All rights reserved.

Main service layer for bot operations. Handles message processing, conversation
management, and coordination between the agent workflow and data repositories.

Key Features:
- Message processing with LangGraph agent workflow
- Conversation history management with windowing
- Automatic summarization for long conversations
- Credential redaction for security
- ReAct response parsing (Thought/Action/Observation/Final Answer)
- Session persistence to Redis and Firestore

Architecture:
User Message → Bot Service → Agent Workflow → Tools → Agent → Bot Service → Response
                    ↓                                              ↓
              Redis (sessions)                             Firestore (logs)
"""

import os
import logging
import re
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from flask import current_app
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from services.agent_workflow import agent_executor
from repository.chat_session_repository import ChatSessionRepository
from repository.message_log_repository import MessageLogRepository


# ===== System Prompts =====
# This defines the bot's personality and behavior
# Customize this for your specific use case

SYSTEM_PROMPT_DEFAULT = """You are a helpful AI assistant. Your role is to assist users with their questions and tasks professionally and efficiently.

**Available Tools:**
1. `knowledge_retriever` - Retrieves information from the knowledge base. Use this for factual questions about the platform or service.

**Tool Usage Policy:**
- When a user asks a factual question, use `knowledge_retriever` to get accurate, up-to-date information.
- Always base your answers on the retrieved context when using the knowledge retriever.
- If the knowledge base doesn't contain relevant information, clearly state that.

**ReAct Policy:**
- Follow ReAct: Thought → (optional) Action → Observation → Final Answer.
- Prefer using tools when available for factual questions.
- Always provide a clear Final Answer to the user.

**Response Guidelines:**
- Be professional and concise
- Provide accurate information
- If you don't know something, say so
- Be helpful and friendly
"""

SYSTEM_PROMPT_TOURIST = """You are a helpful AI travel assistant specialized in helping tourists plan and manage their tours. Your role is to assist tourists with tour planning, bookings, and travel advice.

**Your Expertise:**
- Tour planning and itinerary suggestions
- Destination recommendations and travel advice
- Budget optimization for trips
- Cultural and local insights
- Accessibility and special requirements
- Language and communication support
- Booking and reservation assistance

**Available Tools:**
1. `knowledge_retriever` - Retrieves information from the knowledge base about destinations, tours, and services.

**Response Guidelines:**
- Be warm, welcoming, and enthusiastic about travel
- Provide detailed, practical advice for tourists
- Consider budget constraints and special needs
- Offer multiple options when possible
- Include safety and cultural etiquette tips
- Be patient and explain travel concepts clearly
- Help tourists make informed decisions

**Communication Style:**
- Friendly and encouraging
- Detail-oriented for travel planning
- Proactive in suggesting alternatives
- Empathetic to concerns and preferences
"""

SYSTEM_PROMPT_GUIDE = """You are a professional AI assistant specialized in helping tour guides succeed in their business. Your role is to assist guides with applications, pricing strategies, customer service, and professional development.

**Your Expertise:**
- Writing compelling tour proposals
- Competitive pricing strategies
- Customer service best practices
- Tour planning and execution
- Professional communication with tourists
- Marketing and self-promotion
- Handling special requests and requirements
- Building reputation and getting reviews

**Available Tools:**
1. `knowledge_retriever` - Retrieves information from the knowledge base about guide best practices and platform guidelines.

**Response Guidelines:**
- Be professional and business-focused
- Provide actionable, practical advice
- Help guides differentiate themselves from competition
- Emphasize quality service and professionalism
- Include tips for building long-term success
- Be honest about pricing and market realities
- Support guides in growing their business

**Communication Style:**
- Professional and consultative
- Strategic and business-minded
- Encouraging yet realistic
- Focused on measurable outcomes
- Respectful of guides' expertise while offering insights
"""


def get_system_prompt(user_role: Optional[str] = None) -> str:
    """
    Get the appropriate system prompt based on user role.
    
    Args:
        user_role: User role ('tourist', 'guide', or None)
    
    Returns:
        System prompt string
    """
    if user_role == 'tourist':
        return SYSTEM_PROMPT_TOURIST
    elif user_role == 'guide':
        return SYSTEM_PROMPT_GUIDE
    else:
        return SYSTEM_PROMPT_DEFAULT


class BotService:
    """
    Main service class for bot operations.
    Handles message processing, conversation management, and persistence.
    """
    
    def __init__(self):
        """Initialize the bot service with lazy-loaded dependencies"""
        self.logger = logging.getLogger(__name__)
        self.agent_executor = agent_executor
        self._chat_session_repository = None
        self._message_log_repository = None
        
        # Precompiled patterns to redact sensitive information
        self._credential_patterns = [
            re.compile(r"(password\s*[:=]\s*)(\S+)", flags=re.IGNORECASE),
            re.compile(r"(pwd\s*[:=]\s*)(\S+)", flags=re.IGNORECASE),
            re.compile(r"(pass\s*[:=]\s*)(\S+)", flags=re.IGNORECASE),
            re.compile(r"(\bp:\s*)(\S+)", flags=re.IGNORECASE),
            re.compile(r"(\bpassword\b\s+is\s+)(\S+)", flags=re.IGNORECASE),
            re.compile(r"(api[_-]?key\s*[:=]\s*)(\S+)", flags=re.IGNORECASE),
            re.compile(r"(token\s*[:=]\s*)(\S+)", flags=re.IGNORECASE),
        ]
        
        # Lazy-initialized summarizer LLM
        self._summarizer_llm = None

    # ===== Repository Properties (Lazy Loading) =====
    
    @property
    def chat_session_repository(self):
        """Lazy initialization of chat session repository"""
        try:
            if self._chat_session_repository is None:
                self._chat_session_repository = ChatSessionRepository()
            return self._chat_session_repository
        except Exception as e:
            self.logger.error(f"Error getting chat session repository: {str(e)}")
            return None

    @property
    def message_log_repository(self):
        """Lazy initialization of message log repository"""
        try:
            if self._message_log_repository is None:
                self._message_log_repository = MessageLogRepository()
            return self._message_log_repository
        except Exception as e:
            self.logger.error(f"Error getting message log repository: {str(e)}")
            return None

    # ===== Security: Credential Redaction =====
    
    def _redact_credentials(self, text: str) -> str:
        """
        Mask password-like substrings to avoid leaking secrets in logs/storage.
        
        Args:
            text: Text that may contain sensitive information
            
        Returns:
            Text with sensitive information replaced with ******
        """
        if not text or not isinstance(text, str):
            return ""
        
        redacted = text
        for pattern in self._credential_patterns:
            redacted = pattern.sub(r"\1******", redacted)
        
        return redacted

    # ===== Service Information =====
    
    def get_service_info(self) -> Dict[str, Any]:
        """
        Get service information and status.
        
        Returns:
            Dictionary with service metadata
        """
        try:
            return {
                'service_name': current_app.config.get('BOT_NAME', 'AI Bot'),
                'version': current_app.config.get('BOT_VERSION', '1.0.0'),
                'status': 'running',
                'llm_model': current_app.config.get('LLM_MODEL', 'gemini-2.5-flash')
            }
        except Exception:
            return {
                'service_name': 'AI Bot',
                'version': '1.0.0',
                'status': 'running',
                'llm_model': 'gemini-2.5-flash'
            }

    # ===== Conversation History Management =====
    
    def get_session_history(self, session_id: str) -> List[Dict[str, str]]:
        """
        Get conversation history from Redis.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            List of messages with role, message, and timestamp
        """
        try:
            return self.chat_session_repository.get_conversation_history(session_id)
        except Exception as e:
            self.logger.error(f"Error getting session history: {str(e)}")
            return []

    def get_session_history_from_firestore(self, session_id: str) -> List[Dict[str, str]]:
        """
        Get conversation history from Firestore (persistent storage).
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            List of messages from Firestore
        """
        try:
            return self.message_log_repository.get_all_messages_for_session(session_id)
        except Exception as e:
            self.logger.error(f"Error getting session history from Firestore: {str(e)}")
            return []

    def _get_keep_k(self) -> int:
        """
        Get the number of past messages to include in LLM context.
        
        Returns:
            Number of messages to keep in context window
        """
        try:
            return int(current_app.config.get('MAX_CONVERSATION_HISTORY_MESSAGES', 10))
        except Exception:
            return 10

    # ===== Summarization for Long Conversations =====
    
    def _ensure_summarizer(self):
        """Initialize the summarizer LLM if not already initialized"""
        if self._summarizer_llm is None:
            api_key = os.environ.get('GEMINI_FLASH_API_KEY')
            if not api_key:
                self.logger.warning("GEMINI_FLASH_API_KEY not found. Summarizer disabled.")
                return

            self._summarizer_llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                temperature=0,
                google_api_key=api_key
            )

    def _maybe_summarize_and_prune(self, session_id: str):
        """
        Optionally summarize long conversations and prune to last K messages.
        
        This helps manage context window size for very long conversations.
        
        Args:
            session_id: Unique session identifier
        """
        try:
            if not session_id:
                return
            
            history = self.chat_session_repository.get_conversation_history(session_id) or []
            keep_k = self._get_keep_k()
            
            # Only summarize if conversation is significantly longer than window
            if len(history) <= keep_k * 2:
                return

            # Build conversation text for summarization
            convo_lines = []
            for h in history:
                role = h.get('role', 'user')
                msg = h.get('message', '')
                convo_lines.append(f"{role}: {msg}")
            convo_text = "\n".join(convo_lines)

            # Generate summary
            self._ensure_summarizer()
            if not self._summarizer_llm:
                return
            
            summary_prompt = (
                "Summarize the following conversation between a user and an assistant. "
                "Capture key points, decisions, and any unresolved items. "
                "Keep the summary concise (under 150 words).\n\n" + convo_text
            )
            
            summary = self._summarizer_llm.invoke(summary_prompt).content
            if summary:
                self.chat_session_repository.set_summary(session_id, summary)
            
            # Prune history to last K messages
            pruned = history[-keep_k:]
            self.chat_session_repository.set_conversation_history(session_id, pruned)
            
            self.logger.info(f"Summarized and pruned session {session_id}")
            
        except Exception as e:
            self.logger.warning(f"Summarization/prune skipped: {e}")

    # ===== Message Building for LLM =====
    
    def _build_llm_messages(
        self,
        conversation_history: List[Dict[str, str]],
        session_id: Optional[str],
        input_msg: str,
        user_role: Optional[str] = None
    ) -> List[BaseMessage]:
        """
        Build the message list for LLM invocation.
        
        Includes:
        - System prompt (role-specific)
        - Session identifier (if provided)
        - Conversation summary (if available)
        - Windowed conversation history
        - Current user message
        
        Args:
            conversation_history: Past conversation messages
            session_id: Optional session identifier
            input_msg: Current user message
            user_role: Optional user role for role-specific prompts
            
        Returns:
            List of LangChain messages ready for LLM
        """
        # Gemini doesn't support SystemMessage, so we use HumanMessage for system instructions
        # The LLM is configured with convert_system_message_to_human=True to handle this
        system_prompt = get_system_prompt(user_role)
        messages: List[BaseMessage] = [HumanMessage(content=system_prompt)]
        
        # Include session identifier for tools that need it
        if session_id:
            messages.append(HumanMessage(
                content=f"Current session identifier: {session_id}"
            ))
        
        # Include stored summary if available
        if session_id:
            try:
                summary = self.chat_session_repository.get_summary(session_id)
                if summary:
                    messages.append(HumanMessage(
                        content=f"Context summary: {summary}"
                    ))
            except Exception:
                pass
        
        # Window the history to last K messages
        keep_k = self._get_keep_k()
        window = conversation_history[-keep_k:] if conversation_history else []
        
        for msg in window:
            role = msg.get('role')
            text = msg.get('message', '')
            
            if role == 'user':
                messages.append(HumanMessage(content=text))
            elif role == 'assistant':
                messages.append(AIMessage(content=text))
        
        # Add current user message
        messages.append(HumanMessage(content=input_msg or ""))
        
        return messages

    # ===== Response Parsing =====
    
    def _normalize_ai_content(self, content: Any) -> str:
        """
        Normalize structured AIMessage content into a plain string.
        
        Args:
            content: Content from AIMessage (can be string, list, dict, etc.)
            
        Returns:
            Normalized string content
        """
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                normalized = self._normalize_ai_content(item)
                if normalized:
                    parts.append(normalized)
            return "\n".join(parts).strip()
        if isinstance(content, dict):
            if "text" in content:
                return self._normalize_ai_content(content.get("text"))
            return json.dumps(content, ensure_ascii=False)
        return str(content)

    def _extract_react_sections(self, text: Optional[str]) -> Dict[str, Optional[str]]:
        """
        Extract ReAct sections from agent response.
        
        Parses sections like:
        **Thought**: ...
        **Action**: ...
        **Observation**: ...
        **Final Answer**: ...
        
        Args:
            text: Agent response text
            
        Returns:
            Dictionary with thought, action, observation, final_answer keys
        """
        try:
            if not text or not isinstance(text, str):
                return {
                    "thought": None,
                    "action": None,
                    "observation": None,
                    "final_answer": None
                }

            # Regex to capture each section
            pattern = r"\*{0,2}(Thought|Action|Observation|Final Answer)\*{0,2}\s*:\s*(.*?)\s*(?=\*{0,2}(?:Thought|Action|Observation|Final Answer)\*{0,2}\s*:|$)"
            regex = re.compile(pattern, re.DOTALL | re.IGNORECASE)

            sections: Dict[str, Optional[str]] = {
                "thought": None,
                "action": None,
                "observation": None,
                "final_answer": None,
            }
            
            matches = regex.findall(text)
            for label, content in matches:
                norm = label.strip().lower()
                if norm == "final answer":
                    key = "final_answer"
                else:
                    key = norm
                sections[key] = content.strip() if content is not None else None

            # Fallback: if no sections found, treat entire text as final answer
            if all(v is None for v in sections.values()):
                cleaned = text.strip()
                cleaned = re.sub(r"^\s*\**\s*answer\s*:\s*", "", cleaned, flags=re.IGNORECASE)
                sections["final_answer"] = cleaned

            return sections
            
        except Exception:
            return {
                "thought": None,
                "action": None,
                "observation": None,
                "final_answer": text.strip() if isinstance(text, str) else None
            }

    # ===== Main Message Processing =====
    
    def process_message(
        self,
        input_msg: str,
        session_id: Optional[str] = None,
        user_role: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process user message and return AI response.
        
        This is the main entry point for message processing. It:
        1. Retrieves conversation history
        2. Builds LLM messages with context
        3. Executes agent workflow
        4. Parses response
        5. Saves to Redis and Firestore
        6. Returns formatted response
        
        Args:
            input_msg: User's input message
            session_id: Optional session identifier
            user_role: Optional user role (for context)
            
        Returns:
            Dictionary containing:
            - response: Final answer text
            - message_type: Type of message
            - confidence: Confidence score
            - original_message: User's original message
            - session_id: Session identifier
            - user_role: User role
            - reasoning: ReAct sections (thought, action, observation, final_answer)
        """
        try:
            print(f"\n{'='*60}")
            print(f"User: {self._redact_credentials(input_msg)}")
            print(f"{'='*60}")
            
            # Get conversation history if session_id provided
            conversation_history = []
            if session_id:
                conversation_history = self.get_session_history(session_id)
                print(f"📚 Retrieved {len(conversation_history)} messages from session history")
            
            # Build messages for the agent (with role-specific system prompt)
            messages = self._build_llm_messages(conversation_history, session_id, input_msg, user_role)

            # Execute the agent workflow
            print(f"🤖 Executing agent workflow with role: {user_role or 'default'}...")
            result = self.agent_executor.invoke({"messages": messages})

            # Extract final message from result
            final_message = result["messages"][-1]
            ai_response = ""
            
            if isinstance(final_message, AIMessage):
                ai_response = self._normalize_ai_content(final_message.content)

            if not ai_response:
                ai_response = "I apologize, but I couldn't generate a response at this time."

            print(f"\n{'='*60}")
            print(f"AI Response: {ai_response}")
            print(f"{'='*60}\n")

            # Parse ReAct sections
            react_sections = self._extract_react_sections(ai_response)
            final_answer = react_sections.get("final_answer") or ai_response

            # Save conversation to session history
            if session_id:
                try:
                    # Save to Redis (session cache)
                    self.chat_session_repository.add_message(
                        session_id,
                        'user',
                        self._redact_credentials(input_msg)
                    )
                    self.chat_session_repository.add_message(
                        session_id,
                        'assistant',
                        self._redact_credentials(final_answer)
                    )
                    print(f"✅ Saved conversation to Redis session: {session_id}")
                except Exception as e:
                    self.logger.error(f"Error saving to Redis: {e}")

                # Save to Firestore (persistent storage)
                try:
                    repo = self.message_log_repository
                    if repo:
                        repo.log_message(session_id, self._redact_credentials(input_msg), 'user')
                        repo.log_message(session_id, self._redact_credentials(final_answer), 'bot')
                        print(f"✅ Saved conversation to Firestore for session: {session_id}")
                except Exception as e:
                    self.logger.error(f"Error saving to Firestore: {e}")

                # Optionally summarize and prune
                self._maybe_summarize_and_prune(session_id)

            # Prepare response data
            response_data = {
                "response": final_answer,
                "message_type": "ai_response",
                "confidence": 0.85,
                "original_message": input_msg,
                "session_id": session_id,
                "user_role": user_role,
                "suggestions": [],
                "reasoning": react_sections
            }
            
            self.logger.info(f"✅ Successfully processed message for session {session_id}")
            return response_data
            
        except Exception as e:
            self.logger.error(f"❌ Error processing message: {str(e)}")
            return {
                "response": "I apologize, but I encountered an error processing your message. Please try again.",
                "message_type": "error",
                "confidence": 0.0,
                "original_message": input_msg,
                "session_id": session_id,
                "user_role": user_role,
                "suggestions": [],
                "error": str(e)
            }


# ===== Global Service Instance =====
# Create a singleton instance for use across the application
bot_service = BotService()

