import sys
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
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Load environment variables dynamically from the primary root directory
load_dotenv(REPO_ROOT / ".env")

# Reconfigure your execution paths to look dynamically inside the new src directory tree
VENV_PYTHON = str(REPO_ROOT / ".venv" / "bin" / "python3")
SERVER_SCRIPT = str(REPO_ROOT / "src" / "server" / "hr_mcp_server.py")

CORE_STRATEGY_PROMPT = """You are the Umbrella Corp HR Assistant.
You operate in a high-security environment where PII (Personally Identifiable Information) is tokenized.

--- MANDATORY PROTOCOLS ---
1. AUTHENTICATION FIRST: If 'is_authenticated' returns False or if you haven't called 'authenticate_user', you must refuse all data requests and redirect the user to log in.
2. TOKEN INTEGRITY: You will encounter data in the format [TOKEN_TYPE_ID].
   - NEVER try to guess, invent, or hide these tokens.
   - ALWAYS include them in your response exactly as received.
   - The UI layer will handle the decryption; your job is only to pass the token through.
3. STRUCTURED DATA: When displaying employee lists, always use Markdown tables for clarity.
4. POLICY KNOWLEDGE: Use 'search_policy_documents' for any procedural questions.
   - You MUST provide the "Source" metadata for every policy answer.
5. COMPLIANCE AUDITING: Every single response must be followed by a call to 'save_to_audit'.
   - Pass the user's question and your response (containing tokens) to this tool.

--- TONE ---
Professional, efficient, and security-conscious. Do not apologize for security restrictions.
"""

async def run_conversation():
    memory = SqliteSaver.from_conn_string("checkpoints.sqlite")

    # ONE CLIENT TO RULE THEM ALL
    # We keep this process alive so the server maintains its 'CURRENT_SESSION' state.
    client = MultiServerMCPClient({
        "hr-server": {
            "command": VENV_PYTHON,
            "args": [SERVER_SCRIPT],
            "transport": "stdio"
        }
    })

    print("🛰️ Connecting to HR Infrastructure...")
    tools = await client.get_tools()
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    agent = create_react_agent(llm, tools, checkpointer=memory)

    # --- STEP 1: AUTHENTICATION ---
    print("\n🔐 UMBRELLA CORP LOGIN")
    uname = input("Username: ").strip()
    upass = input("Password: ").strip()

    # The agent calls 'authenticate_user'. The server then saves the role in memory.
    auth_msg = HumanMessage(content=f"Please log me in with username '{uname}' and password '{upass}' using the authentication tool.")
    auth_result = await agent.ainvoke({"messages": [auth_msg]})

    user_context = None
    # Look for the tool response to get user details
    for msg in reversed(auth_result["messages"]):
        if isinstance(msg, ToolMessage):
            try:
                data = json.loads(msg.content)
                if data.get("status") == "success":
                    user_context = data
                    break
            except: continue

    if not user_context:
        print("❌ Login Failed.")
        await client.close()
        return

    user_id = user_context["user_id"]
    config = {"configurable": {"thread_id": user_id}}
    messages = [SystemMessage(content=CORE_STRATEGY_PROMPT + f"\nActive Session: {user_context['first_name']} | Role: {user_context['role']}")]

    print(f"\n✅ Access Granted. Welcome, {user_context.get('first_name', 'User')}!")

    # --- STEP 2: CHAT LOOP ---
    while True:
        try:
            user_input = input("\nYou: ").strip()
            if user_input.lower() in ["q", "quit", "exit"]: break

            messages.append(HumanMessage(content=user_input))
            result = await agent.ainvoke({"messages": messages}, config=config)
            messages = result["messages"]

            # Source detection for audit
            source_used = "General"
            node_path = "generation_node"
            for m in reversed(messages):
                if isinstance(m, ToolMessage):
                    node_path = m.name
                    source_used = "SQL" if "query" in m.name else "Vector"
                    break

            raw_text = messages[-1].content

            # --- STEP 3: DE-TOKENIZATION (For User Display) ---
            token_pattern = r"\[TOKEN_[A-Z0-9_]+\]"
            tokens = re.findall(token_pattern, raw_text)
            display_text = raw_text

            if tokens:
                for t in set(tokens):
                    # We call the tool directly through the client
                    resp = await client.send_request("hr-server", "tools/call", {
                        "name": "demask_token_payload",
                        "arguments": {"token": t}
                    })
                    # FastMCP returns { "content": [{ "type": "text", "text": "..." }] }
                    real_val = resp['content'][0]['text']
                    display_text = display_text.replace(t, real_val)

            print(f"\nAssistant: {display_text}")

            # --- STEP 4: AUDIT ---
            await client.send_request("hr-server", "tools/call", {
                "name": "save_to_audit",
                "arguments": {
                    "user_id": user_id,
                    "question": user_input,
                    "answer": raw_text, # Audit the tokens, not the secret data
                    "source": source_used,
                    "node_path": node_path
                }
            })

        except Exception as e:
            print(f"❌ Error: {e}")
            break

    await client.close()

if __name__ == "__main__":
    asyncio.run(run_conversation())