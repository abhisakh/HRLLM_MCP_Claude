import sys
# Ensures your virtual environment packages are discoverable
sys.path.insert(0, "/Users/abhisakhsarma/Software_Engineering/Master_School/MCP/my_mcp_project/.venv/lib/python3.13/site-packages")

import asyncio
import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

# Load environment variables from the local path
load_dotenv(Path(__file__).parent / ".env")

VENV_PYTHON = "/Users/abhisakhsarma/Software_Engineering/Master_School/MCP/my_mcp_project/.venv/bin/python3"
SERVER_SCRIPT = "/Users/abhisakhsarma/Software_Engineering/Master_School/MCP/my_mcp_project/hr_mcp_server.py"

CORE_STRATEGY_PROMPT = """You are the Umbrella Corp HR Assistant.
Current Session: {first_name} (ID: {user_id}) | Role: {role}

--- DATA HANDLING RULES ---
1. SQL SOURCE (Structured): When using 'query_employees' or 'get_salary_stats':
   - If data is empty, say: "No employee records matched that criteria."
   - DO NOT mention 'supervisor_id' unless specifically asked.
   - If the user asks for 'contact info', prioritize Email and Phone Number only.
   - For lists, use a Markdown Table.

2. VECTOR SOURCE (Unstructured): When using 'search_policy_documents':
   - Synthesize the answer from the content provided.
   - ALWAYS cite the source (e.g., 'Source: Employee_Handbook_2023.pdf').
   - If the answer isn't in the context, say: "I'm sorry, our policy documents don't cover that specific detail."

3. SECURITY & PII:
   - Your role is {role}.
   - You will see system data values masked as tokens like [TOKEN_SALARY_XXXX] or [TOKEN_ADDRESS_XXXX].
   - Treat tokens as real placeholders. Do NOT attempt to alter, invent, or truncate token strings.
   - Print tokens unmodified in your final response text exactly as provided by tools. The platform UI resolves them.

4. LOGGING:
   - You MUST call 'save_to_audit' after every successful response.
"""

def summarize_history(messages, llm):
    """Summarizes past interaction blocks to keep context compressed."""
    chat_text = "\n".join([f"{m.type}: {m.content}" for m in messages[-8:]])
    summary = llm.invoke([
        SystemMessage(content="Summarize this HR chat briefly. Keep names, specific requests, and any active [TOKEN_...] placeholders intact."),
        HumanMessage(content=chat_text)
    ])
    return summary.content

async def run_conversation():
    # 1. PERSISTENT STORAGE FOR CHAT CHECKPOINTS
    memory = SqliteSaver.from_conn_string("checkpoints.sqlite")

    # 2. SEED CLIENT: BOOT A TEMPORARY PROCESS CONTEXT FOR USER AUTHENTICATION ONLY
    # This prevents unauthenticated context loops from hijacking primary runtime environments
    init_env = os.environ.copy()
    init_env["SESSION_ROLE"] = "employee"  # Start with minimum default clearance parameters

    bootstrap_client = MultiServerMCPClient({
        "hr-server": {
            "command": VENV_PYTHON,
            "args": [SERVER_SCRIPT],
            "transport": "stdio",
            "env": init_env
        }
    })

    print("🛰️ Establishing Secure Handshake with Authentication Node...")
    auth_tools = await bootstrap_client.get_tools()
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    auth_agent = create_react_agent(llm, auth_tools, checkpointer=memory)

    # --- STEP 1: AUTHENTICATION ---
    print("\n🔐 UMBRELLA CORP LOGIN")
    uname = input("Username: ").strip()
    upass = input("Password: ").strip()

    # Request credentials processing through agent node architecture
    auth_result = await auth_agent.ainvoke({"messages": [HumanMessage(content=f"Authenticate user {uname} with password {upass}")]})

    user_context = None
    for msg in reversed(auth_result["messages"]):
        if isinstance(msg, ToolMessage):
            try:
                data = json.loads(msg.content)
                if data.get("status") == "success":
                    user_context = data
                    break
            except Exception:
                continue

    if not user_context:
        print("❌ Login Failed: Invalid Credentials.")
        # Safely disconnect baseline stream channels before termination
        await bootstrap_client.close()
        return

    # Shutdown the temporary bootstrap initialization channel process cleanly
    await bootstrap_client.close()

    # --- STEP 2: IMMUTABLE SESSION CONFIGURATION ---
    user_id = user_context["user_id"]
    role = user_context["role"]
    config = {"configurable": {"thread_id": user_id}}

    # 🔒 RE-SPAWN PRIMARY MCP SERVER ISOLATED AT OPERATING SYSTEM LEVEL WITH TRUE VALIDATED ROLE
    server_env = os.environ.copy()
    server_env["SESSION_ROLE"] = str(role)

    client = MultiServerMCPClient({
        "hr-server": {
            "command": VENV_PYTHON,
            "args": [SERVER_SCRIPT],
            "transport": "stdio",
            "env": server_env
        }
    })

    print(f"🔒 Spawning Isolated Environment Process for Role: {role.upper()}...")
    tools = await client.get_tools()
    agent = create_react_agent(llm, tools, checkpointer=memory)

    system_msg = SystemMessage(content=CORE_STRATEGY_PROMPT.format(**user_context))
    messages = [system_msg]

    print(f"\n✅ Access Granted. Welcome, {user_context['first_name']}!")
    print("-" * 50)

    # --- STEP 3: CHAT LOOP ---
    while True:
        try:
            user_input = input("You: ").strip()
            if user_input.lower() in ["q", "quit", "exit"]:
                break
            if not user_input:
                continue

            messages.append(HumanMessage(content=user_input))
            result = await agent.ainvoke({"messages": messages}, config=config)
            messages = result["messages"]

            # --- STEP 4: DYNAMIC SOURCE DETECTION ---
            source_used = "General"
            node_path = "generation_node"
            for m in reversed(messages):
                if isinstance(m, ToolMessage):
                    node_path = m.name
                    source_used = "SQL" if "query" in m.name or "stats" in m.name else "Vector"
                    break

            raw_response_text = messages[-1].content

            # --- 🛡️ CLIENT-SIDE PII DE-TOKENIZATION INTERCEPTION ---
            token_pattern = r"\[TOKEN_[A-Z0-9_]+\]"
            tokens_found = re.findall(token_pattern, raw_response_text)

            hr_visible_text = raw_response_text

            if tokens_found:
                for token in set(tokens_found):
                    try:
                        # Call the demask tool directly via client payload bypassing Claude context frame history
                        # Notice: No 'role' parameter is sent. Server extracts permissions out of server_env["SESSION_ROLE"]
                        demask_res = await client.send_request(
                            "hr-server",
                            "tools/call",
                            {"name": "demask_token_payload", "arguments": {"token": token}}
                        )
                        # Parse out data arrays cleanly based on expected standard FastMCP message envelopes
                        content_list = demask_res.get("content", [{}])
                        real_value = content_list[0].get("text", token) if content_list else token
                        hr_visible_text = hr_visible_text.replace(token, real_value)
                    except Exception:
                        hr_visible_text = hr_visible_text.replace(token, f"[ERR_RESOLVING_TOKEN]")

            print(f"\nAssistant: {hr_visible_text}")

            # --- STEP 5: AUTOMATIC AUDITING ---
            audit_trigger = (f"Internal: save_to_audit(user_id='{user_id}', "
                             f"question='{user_input}', answer='[REDACTED_PII_LOG]', "
                             f"source='{source_used}', node='{node_path}')")
            await agent.ainvoke({"messages": [HumanMessage(content=audit_trigger)]}, config=config)

            # --- STEP 6: CONTEXT COMPRESSION ---
            if len(messages) > 12:
                print("📝 Optimizing context window...")
                summary = summarize_history(messages, llm)
                messages = [system_msg, SystemMessage(content=f"Summary of previous turns: {summary}"), messages[-1]]

            print("-" * 50)

        except Exception as e:
            print(f"\n❌ System Error: {e}")
            break

    # Clean disconnection on clean application termination
    await client.close()

if __name__ == "__main__":
    try:
        asyncio.run(run_conversation())
    except KeyboardInterrupt:
        print("\nSession ended cleanly.")
