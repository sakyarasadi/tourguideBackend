"""
LangGraph Agent Workflow
=========================
AI Chatbot Boilerplate - A proprietary asset of Exe.lk

Author: A B Geethan Imal
Organization: Exe.lk
Copyright (c) 2024 Exe.lk. All rights reserved.

This module defines the LangGraph workflow for the bot's ReAct (Reasoning + Acting) loop.

The workflow:
1. Receives user message
2. LLM decides whether to use tools or provide final answer
3. If tools needed, executes them and returns to LLM
4. LLM processes tool output and provides final answer
5. Returns response to user

Key Components:
- AgentState: Maintains conversation state (messages)
- call_model: Invokes LLM with optional RAG context injection
- should_continue: Decides next step (tools or end)
- build_agent_workflow: Factory function to create workflow with custom tools

RAG Integration:
When a knowledge retrieval tool is used, the workflow automatically injects
RAG context into the LLM's prompt to ground the response in retrieved knowledge.
"""

import os
from typing import TypedDict, Annotated, List, Literal
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI

# Import tools that will be available to the agent
from tools.knowledge_retriever import knowledge_retriever
# from tools.example_custom_tool import example_custom_tool  # Uncomment to add custom tools

# Define the default toolset for the agent
# Add or remove tools here to customize bot capabilities
DEFAULT_TOOLS = [
    knowledge_retriever,
    # example_custom_tool,  # Uncomment to enable
]


# ===== Agent State Definition =====
class AgentState(TypedDict):
    """
    Represents the state of the agent workflow.
    
    Attributes:
        messages: List of conversation messages (user, AI, tool, system)
                 Uses add_messages reducer to append new messages
    """
    messages: Annotated[List[BaseMessage], add_messages]


# ===== LLM Model Call Function Factory =====
def create_call_model(llm_with_tools):
    """
    Create a model call function bound to a specific LLM with tools.
    
    This function handles:
    - Invoking the LLM with conversation context
    - RAG context injection for knowledge retrieval tools
    - Error handling
    
    Args:
        llm_with_tools: LLM instance with tools bound to it
        
    Returns:
        Function that processes agent state and returns updated state
    """
    
    def call_model(state: AgentState) -> AgentState:
        """
        Invoke the LLM and optionally inject RAG context.
        
        RAG Context Injection:
        If the last message is a ToolMessage from a knowledge retrieval tool,
        we inject a system message that grounds the LLM's response in the
        retrieved context.
        
        Args:
            state: Current agent state with messages
            
        Returns:
            Updated state with LLM response
        """
        try:
            messages = list(state["messages"])

            # ===== RAG Context Injection Logic =====
            # Check if we just received a tool output that contains knowledge base context
            if messages and isinstance(messages[-1], ToolMessage):
                retrieved_context = messages[-1].content

                # Check if the previous message was an AI tool call request
                if len(messages) >= 2 and isinstance(messages[-2], AIMessage) and messages[-2].tool_calls:
                    # Check if any of the tools called were knowledge retrieval tools
                    rag_tool_names = {"knowledge_retriever", "knowledge_retriever_lotogram"}
                    called_tools = {tc.get("name") for tc in messages[-2].tool_calls}
                    
                    if rag_tool_names.intersection(called_tools):
                        # Find the original user query
                        original_query_message = next(
                            (m for m in messages if isinstance(m, HumanMessage)), 
                            None
                        )
                        original_query = (
                            original_query_message.content 
                            if original_query_message 
                            else "The user asked a question."
                        )

                        # Create a system instruction to ground the LLM's response
                        # Use HumanMessage since Gemini doesn't support SystemMessage
                        rag_instruction = HumanMessage(
                            content=f"""
--- CONTEXT RETRIEVED FROM KNOWLEDGE BASE ---
{retrieved_context}
---

Based **only** on the above retrieved context, answer the user's query.
If the context is insufficient to fully answer the question, clearly state what is known and what cannot be determined from the available information.

Original Query: {original_query}
                            """
                        )
                        
                        # Inject the RAG instruction for the LLM to use
                        messages.append(rag_instruction)
                        print("📝 RAG context injected into LLM prompt")

            # ===== Invoke the LLM =====
            response = llm_with_tools.invoke(messages)

            # ===== Debug Logging =====
            if isinstance(response, AIMessage):
                if response.tool_calls:
                    tool_names = ", ".join(tc.get("name", "?") for tc in response.tool_calls)
                    print(f"🔧 LLM requested tools: {tool_names}")
                else:
                    print("💬 LLM returned a final answer")

            return {"messages": [response]}

        except Exception as e:
            print(f"❌ Error in call_model: {str(e)}")
            error_message = AIMessage(
                content=f"I apologize, but I encountered an error: {str(e)}"
            )
            return {"messages": [error_message]}

    return call_model


# ===== Conditional Edge Function =====
def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """
    Determine whether to execute tools or end the workflow.
    
    This is the decision point in the ReAct loop:
    - If LLM requested tool calls -> execute tools
    - If LLM provided final answer -> end workflow
    
    Args:
        state: Current agent state
        
    Returns:
        "tools" to execute tools, "end" to finish
    """
    try:
        last_message = state["messages"][-1]
        
        # Check if the last message from LLM has tool calls
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            tool_names = ", ".join(tc.get("name", "?") for tc in last_message.tool_calls)
            print(f"➡️  Executing tools: {tool_names}")
            return "tools"
        
        # No tool calls means we have a final answer
        return "end"
        
    except Exception as e:
        print(f"❌ Error in should_continue: {str(e)}")
        return "end"


# ===== Workflow Factory Function =====
def build_agent_workflow(tools_list=None):
    """
    Create a LangGraph workflow with specified tools.
    
    This factory function allows you to create custom agent workflows
    with different tool configurations.
    
    Args:
        tools_list: List of LangChain tools to make available to the agent
                   If None, uses DEFAULT_TOOLS
    
    Returns:
        Compiled LangGraph workflow ready for execution
        
    Example:
        # Use default tools
        agent = build_agent_workflow()
        
        # Use custom tools
        from tools.custom import my_tool
        agent = build_agent_workflow([knowledge_retriever, my_tool])
    """
    if tools_list is None:
        tools_list = DEFAULT_TOOLS
    
    print(f"🔧 Building agent workflow with {len(tools_list)} tools:")
    for tool in tools_list:
        print(f"   - {tool.name}")
    
    # Get Gemini API key from environment
    api_key = os.environ.get("GEMINI_FLASH_API_KEY")
    if not api_key:
        raise ValueError("⚠️ Missing environment variable: GEMINI_FLASH_API_KEY")
    
    # Get LLM configuration from environment with defaults
    model_name = os.environ.get('LLM_MODEL', 'gemini-2.5-flash')
    temperature = float(os.environ.get('LLM_TEMPERATURE', '0'))
    
    print(f"🤖 Using LLM: {model_name} (temperature: {temperature})")
    
    # Initialize the LLM
    # Note: convert_system_message_to_human=True because Gemini doesn't support SystemMessage
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        temperature=temperature,
        google_api_key=api_key,
        convert_system_message_to_human=True,  # Convert SystemMessage to HumanMessage for Gemini compatibility
    )
    
    # Bind tools to the LLM
    # With langchain-google-genai 4.0.0+, bind_tools is supported
    llm_with_tools = llm.bind_tools(tools_list)
    
    # Create the call_model function
    call_model = create_call_model(llm_with_tools)
    
    # Create tool execution node
    # Create a tool map for quick lookup
    tool_map = {tool.name: tool for tool in tools_list}
    
    def tool_node(state: AgentState) -> AgentState:
        """
        Execute tools requested by the LLM.
        
        This function processes tool calls from the last AI message,
        executes the tools, and returns ToolMessage results.
        """
        messages = list(state["messages"])
        last_message = messages[-1]
        
        # Get tool calls from the last AI message
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            tool_messages = []
            # Execute each tool call
            for tool_call in last_message.tool_calls:
                tool_name = tool_call.get("name")
                tool_args = tool_call.get("args", {})
                tool_id = tool_call.get("id")
                
                if tool_name in tool_map:
                    try:
                        # Execute the tool
                        tool = tool_map[tool_name]
                        result = tool.invoke(tool_args)
                        
                        # Create a ToolMessage with the result
                        tool_message = ToolMessage(
                            content=str(result),
                            tool_call_id=tool_id
                        )
                        tool_messages.append(tool_message)
                        print(f"✅ Executed tool: {tool_name}")
                    except Exception as e:
                        # Create error message
                        error_message = ToolMessage(
                            content=f"Error executing {tool_name}: {str(e)}",
                            tool_call_id=tool_id
                        )
                        tool_messages.append(error_message)
                        print(f"❌ Error executing tool {tool_name}: {str(e)}")
                else:
                    # Tool not found
                    error_message = ToolMessage(
                        content=f"Tool {tool_name} not found",
                        tool_call_id=tool_id
                    )
                    tool_messages.append(error_message)
                    print(f"⚠️ Tool not found: {tool_name}")
            
            return {"messages": tool_messages}
        
        # No tool calls, return empty
        return {"messages": []}
    
    # ===== Build the LangGraph Workflow =====
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("llm", call_model)
    workflow.add_node("tools", tool_node)
    
    # Set entry point
    workflow.set_entry_point("llm")
    
    # Add conditional edge from LLM
    # After LLM runs, decide whether to execute tools or end
    workflow.add_conditional_edges(
        "llm",
        should_continue,
        {
            "tools": "tools",  # Execute tools
            "end": END,        # End workflow
        }
    )
    
    # Add edge from tools back to LLM
    # After tools execute, go back to LLM to process results
    workflow.add_edge("tools", "llm")
    
    # Compile the workflow
    compiled_workflow = workflow.compile()
    
    print("✅ Agent workflow compiled successfully")
    
    return compiled_workflow


# ===== Initialize Default Agent =====
# Create a default agent instance that can be imported and used immediately
agent_executor = build_agent_workflow()

print("✅ Default agent executor ready for use")

