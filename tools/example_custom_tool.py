"""
Example Custom Tool
===================
This is a template showing how to create custom tools for your bot.

Key Components:
1. @tool decorator - Makes the function available to the LangChain agent
2. Comprehensive docstring - Tells the LLM when and how to use the tool
3. Type hints - Specify expected parameter types
4. Error handling - Gracefully handle failures
5. Logging - Print debug information

To create a new tool:
1. Copy this file and rename it
2. Update the function name and docstring
3. Implement your business logic
4. Import and add it to the tools list in agent_workflow.py
"""

from langchain_core.tools import tool
import requests
from typing import Optional


@tool
def example_custom_tool(parameter1: str, parameter2: Optional[int] = None) -> str:
    """
    Example tool that demonstrates how to create custom tools.
    
    USE THIS TOOL WHEN:
    - The user asks for [specific use case]
    - You need to [what this tool does]
    
    DO NOT USE THIS TOOL FOR:
    - [Cases where this tool is not appropriate]
    
    IMPORTANT: [Any critical information the LLM should know]
    
    Args:
        parameter1: Description of first parameter
        parameter2: Optional description of second parameter
        
    Returns:
        Result message or data from the tool execution
    """
    try:
        print(f"\n🔧 Example Custom Tool called with:")
        print(f"  parameter1: {parameter1}")
        print(f"  parameter2: {parameter2}")
        
        # === Your Business Logic Here ===
        # Examples:
        # - Call external API
        # - Query database
        # - Process data
        # - Perform calculations
        
        # Example: Mock API call
        result = {
            'status': 'success',
            'message': f'Processed {parameter1}',
            'parameter2': parameter2
        }
        
        # Example: External API call (commented out)
        # response = requests.post(
        #     'https://api.example.com/endpoint',
        #     json={'param': parameter1},
        #     timeout=10
        # )
        # if response.ok:
        #     result = response.json()
        # else:
        #     return f"API error: {response.status_code}"
        
        print(f"✅ Tool result: {result}")
        return str(result)
        
    except requests.exceptions.Timeout:
        error_msg = "Request timed out. Please try again."
        print(f"❌ {error_msg}")
        return error_msg
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error: {str(e)}"
        print(f"❌ {error_msg}")
        return error_msg
        
    except Exception as e:
        error_msg = f"Unexpected error in example_custom_tool: {str(e)}"
        print(f"❌ {error_msg}")
        return error_msg


# === Additional Tool Examples ===

@tool
def simple_calculation_tool(number: int) -> str:
    """
    Simple example tool that performs a calculation.
    
    USE THIS TOOL WHEN:
    - The user asks to square a number
    
    Args:
        number: The number to square
        
    Returns:
        The squared result as a string
    """
    try:
        result = number ** 2
        return f"The square of {number} is {result}"
    except Exception as e:
        return f"Error calculating: {str(e)}"


@tool
def data_lookup_tool(lookup_id: str) -> str:
    """
    Example tool showing how to look up data from a data source.
    
    USE THIS TOOL WHEN:
    - The user provides an ID and wants to look up information
    
    Args:
        lookup_id: The identifier to look up
        
    Returns:
        Information about the lookup ID
    """
    try:
        # Mock data - replace with actual database query or API call
        mock_database = {
            '123': {'name': 'Item A', 'status': 'active'},
            '456': {'name': 'Item B', 'status': 'pending'},
        }
        
        if lookup_id in mock_database:
            data = mock_database[lookup_id]
            return f"Found: {data['name']}, Status: {data['status']}"
        else:
            return f"No data found for ID: {lookup_id}"
            
    except Exception as e:
        return f"Error looking up data: {str(e)}"


# === Tips for Creating Effective Tools ===
"""
1. DOCSTRING IS CRITICAL
   - The LLM reads the docstring to decide when to use the tool
   - Be specific about when to use it and when NOT to use it
   - Include examples if helpful

2. PARAMETER TYPES
   - Use type hints (str, int, bool, Optional[type])
   - LangChain validates types before calling your tool
   - Make optional parameters Optional[type] = None

3. RETURN VALUES
   - Always return a string (LangChain requirement)
   - Format structured data as JSON strings if needed
   - Include error messages in the return value

4. ERROR HANDLING
   - Wrap tool logic in try/except
   - Return user-friendly error messages
   - Log errors for debugging

5. TESTING
   - Test tools independently before adding to agent
   - Verify they work with different inputs
   - Check error cases

6. PERFORMANCE
   - Keep tools fast (< 5 seconds if possible)
   - Use timeouts for external calls
   - Consider caching if appropriate

7. SECURITY
   - Validate and sanitize inputs
   - Don't expose sensitive information in returns
   - Use environment variables for credentials
"""

