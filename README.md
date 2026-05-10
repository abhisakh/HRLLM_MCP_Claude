# Umbrella Corp HR Management Engine (Model Context Protocol Hub)

An advanced execution hub demonstrating the **Model Context Protocol (MCP)** by decoupling AI reasoning from high-privilege corporate data layers. This architecture implements a zero-exposure environment where sensitive PII (Salaries, Bank Details, Addresses) is masked directly at the database engine cursor level before entering the LLM's context window.

## 🏗️ System Architecture

```text
               +----------------------------------------+

               |          User Terminal / Prompt        |
               +----------------------------------------+
                                   │
                                   ▼
               +----------------------------------------+

               |        src/client/hr_agent.py          |
               |      (LangGraph Reactive Client)       |
               +----------------------------------------+
                                   │
                    Model Context Protocol (Stdio)
                                   │
                                   ▼
               +----------------------------------------+

               |       src/server/hr_mcp_server.py      |
               |       (FastMCP Layer + SQLite UDF)     |
               +----------------------------------------+
                  │                                  │
          SQL Context Gate                   Semantic Queries
                  │                                  │
                  ▼                                  ▼
+-----------------------------------+   +--------------------------+

|          hr_database.db           |   |      Pinecone Vector     |
|   (Relational Personnel Records)  |   |   (Unstructured Policy)  |
+-----------------------------------+   +--------------------------+
```

## 🛡️ Core Engineering Highlights

*   **SQL-Level Data Masking Gating**: Implements custom SQLite User-Defined Functions (`ENFORCE_PII_POLICY`) running inside the core query statement execution context. If permissions criteria are unmet, data is substituted with randomly generated tracking hashes before leaving the database driver memory heap.
*   **Operating System Level Role Isolation**: Removes the `role` parameter entirely from tools exposed to the LLM. Roles are bound directly to the sub-process environment configuration states (`os.getenv("SESSION_ROLE")`), preventing any parameter-spoofing prompt injections.
*   **Two-Pass De-Tokenization Rendering**: The client intercepts the token payload (`[TOKEN_SALARY_XXXX]`) outside of the agent's memory framework. It programmatically resolves tokens and displays clean values directly onto the HR Specialist's terminal view, ensuring that long-term LLM session histories and external server audits remain completely PII-blind.

## 🚀 End-to-End System Installation & Configuration Guide

This workspace features a decoupled architectural layout, allowing you to run the system in two separate operational environments depending on your engineering target:
1. **Local Developer Console Mode**: A terminal-based simulation using our custom client script to verify execution outputs and automated audit database pipelines.
2. **Enterprise Copilot Mode**: Local registration with the native Claude Desktop client application to drive isolated, sandboxed Claude Project workspaces featuring interactive HTML data dashboard rendering.

---

### 📦 Phase 1: Local Dependency & Data Layer Initialization

Before initializing either client environment, you must build your local isolated package dependencies and seed the local database storage engines.

1. Clone the repository and navigate to your workspace root directory:
   ```bash
   git clone github.com
   cd umbrella-corp-hr-mcp
   ```

2. Establish your local isolated Python virtual environment container:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Upgrade your package manager and mount your explicit, version-frozen system dependencies:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   pip install -e .
   ```

4. Instantiate your localized environment variable storage file:
   ```bash
   cp .env.example .env
   ```
   Open the newly generated `.env` file using a text editor and populate your live API authentication strings:
   ```ini
   OPENAI_API_KEY=sk-proj-YOUR_ACTUAL_OPENAI_KEY_STREAM
   PINECONE_API_KEY=pcsk_YOUR_ACTUAL_PINECONE_KEY_STREAM
   PINECONE_INDEX_NAME=hr-policies-index
   ```

5. Execute the cryptographic personnel seeding engine to construct table layouts in the correct relational constraint sequence:
   ```bash
   python src/database/seed_db.py
   ```
   *CRITICAL DESIGN NOTE: Take explicit note of the usernames (e.g., `john_3619`), generated IDs (`user_3619`), and mapped roles (`hr`, `admin`, `employee`) printed to your console. These profiles match your hashed database parameter tables and are required for downstream authentication testing loops.*

---

### 💻 Phase 2: Mode 1 - Terminal Execution Engine (`hr_agent.py`)

This mode handles multi-turn conversation parsing, LangGraph memory persistence, and client-side token interception entirely within a terminal console window.

1. Launch the interactive client script:
   ```bash
   python src/client/hr_agent.py
   ```
2. Enter a valid username and the password combination (`password123`) generated during the database seeding phase.
3. Once authenticated, input queries naturally (e.g., `"Show me the profile for user_3619"` or `"What are our rules regarding parental time off?"`).
4. Review the outputs to verify that your terminal intercepts `[TOKEN_SALARY_XXXX]` parameters outside the LLM context, swaps them in memory, and prints real unmasked values cleanly to the operator screen.
5. Type `exit` or `logout` to cleanly commit the final compliance logs and kill the sub-process sockets.

---

### 🖥️ Phase 3: Mode 2 - Claude Desktop Application System Registration

This process links your custom FastMCP Python data server directly into the system layer of the native Claude Desktop interface.

#### Step 1: Open the Claude Desktop Settings Configuration File
Locate and open the global configuration manifest file used by Claude Desktop using a text editor:
*   **macOS Path**: `~/Library/Application Support/Claude/claude_desktop_config.json`
*   **Windows Path**: `%APPDATA%\Claude\claude_desktop_config.json`

#### Step 2: Register the Sub-Process Execution Parameters
Paste the configuration layout block below directly inside the `mcpServers` tracking object array. You **must** replace `YOUR_USER_NAME` with your actual machine root folder username to point explicitly to your absolute virtual environment bin file and Python scripts:

```json
{
  "mcpServers": {
    "hr-assistant": {
      "command": "/Users/YOUR_USER_NAME/umbrella-corp-hr-mcp/.venv/bin/python3",
      "args": [
        "/Users/YOUR_USER_NAME/umbrella-corp-hr-mcp/src/server/hr_mcp_server.py"
      ],
      "env": {
        "OPENAI_API_KEY": "YOUR_OPENAI_API_KEY_HERE",
        "PINECONE_API_KEY": "YOUR_PINECONE_API_KEY_HERE",
        "PINECONE_INDEX_NAME": "YOUR_PINECONE_INDEX_NAME_HERE"
      }
    }
  }
}
```

#### Step 3: Verify Tool Schema Mapping and Active Permissions Status
1. Completely restart your Claude Desktop application to reload system sockets and initialize handshakes.
2. Click the **`+` (Attachment/Integrations)** menu icon inside any input window box, go to **Connectors**, and ensure `hr-assistant` is visible with its tracking toggle switched **On (Blue)**.
3. Navigate to your application global settings dashboard (`Customize` -> `Connectors` -> Click on **`hr-assistant`** under Local Development):
   * Confirm that exactly **12 operational tools** are active and mapped under the `Other tools` registry block (spanning `query_employees` through `demask_token_payload`).
   * Ensure that the execution permission setting dropdown is explicitly configured to **`Needs approval`**. This guarantees a human-in-the-loop verification prompt displays before Claude executes queries against your dataset.

---

### 📂 Phase 4: Mode 3 - Isolated Claude Project Sandbox Deployment

This phase builds a secure, dedicated workspace container inside Claude to lock down behavior prompts and automatically expose your backend tool schema matrices.

#### Step 1: Construct the New Workspace Container
1. Click on **Projects** in the primary navigation sidebar array inside the Claude application.
2. Click on the **`New project`** command button in the upper right corner of the workspace layout.
3. Name the container exactly: **`Umbrella HR Control`**
4. Set the descriptive metadata statement to document the system limits:
   * *"Production HR interface connected to local SQLite data pools and Pinecone policy indexes via Model Context Protocol (MCP)."*

#### Step 2: Inject the Two-Pass System Prompt Manifesto
1. Inside the newly generated project dashboard workspace, locate the **Instructions** block panel at the bottom right and click the **Edit (Pencil)** icon to trigger the **`Set project instructions`** configuration modal window.
2. Open your local project file `prompts/claude_desktop.md` and copy the entire plaintext payload text block.
3. Paste the contents directly into the text input area of the modal panel.
4. Verify that all security clauses are intact—including the `--- IMPORTANT SECURITY PARADIGM SHIFT ---` tracking headers, the server-side OS injection variable warnings, and the two-pass token masking requirements.
5. Click **`Save instructions`** to lock down the behavior profile across all future communication streams.

#### Step 3: Run Secure Production Queries
1. Click **`New chat`** within your isolated `Umbrella HR Control` Project container interface.
2. Paste your system-level authentication instructions straight into your new chat pane to trigger your login interface: `"Authenticate user john_3619 with password password123"` (substitute with your actual seeded profile metadata properties).
3. Claude will read your custom instructions and generate your modern enterprise landing login interface cleanly inside a visual **Claude Artifact panel**.
4. Use the interface to execute secure, tokenized data retrievals. The underlying `hr_mcp_server.py` engine masks row values seamlessly, and Claude translates them dynamically *only* within your localized HTML framework view.



## 🔍 Phase : Debugging & Integration Auditing via MCP Inspector

To verify, log, and inspect your custom tool schemas without booting up Claude Desktop, use the official **Model Context Protocol Inspector** utility. This local web diagnostic interface tests tool responses, parameters, and database state mappings in real time.

### 🛠️ Step 1: Prepare the Code for Web/Inspector Mode (SSE)
Before starting the inspector, open `src/server/hr_mcp_server.py` in your text editor. Locate the main execution block at the bottom of the script and ensure the server runs with explicit `sse` transport transport layers:

```python
# Modified for Local Debugging / Web Inspector mode
if __name__ == "__main__":
    mcp.run(transport="sse")  # ❌ This tracking state is strictly for web/Inspector use
```

### 🛰️ Step 2: Spin Up the Concurrent Communication Nodes
Open **two separate terminal window panes** in your workspace directory to launch the server stack and web client:

1. **Terminal 1**: Start your localized Python server process to begin listening for Server-Sent Events on port 8000:
   ```bash
   source .venv/bin/activate
   python src/server/hr_mcp_server.py
   ```
2. **Terminal 2**: Execute the official npm model context protocol package installer tool to launch the local web inspector panel automatically:
   ```bash
   npx @modelcontextprotocol/inspector http://localhost:8000/sse
   ```

### 🎛️ Step 3: Establish the Web Console Connection
1. Your browser will instantly open a new diagnostic tab running at: `http://localhost:3000` (or the console URL printed in Terminal 2).
2. Inside the configuration panel card layout, configure these connection fields:
   * **Transport Type**: Select `SSE` from the dropdown selector.
   * **URL**: Input `http://localhost:8000/sse` into the text box.
3. Click the high-contrast **`Connect`** command button.
4. Navigate through the tabs to evaluate tool signatures, test parameter input values (such as querying `user_3619`), and confirm that the SQL policy gates correctly substitute tracking tokens.

---

### 🛡️ Step 4: Reverting Channels Back to Claude Desktop (Stdio Production Mode)

Once you finish auditing your tools, you must teardown the SSE endpoints and switch back to standard I/O streams to avoid connection errors in Claude Desktop.

1. Go back to your active terminal panes and shut down both running programs by pressing **`Ctrl + C`** in each window.
2. Re-open `src/server/hr_mcp_server.py` in your text editor and update the main execution block at the bottom. Revert the configuration back to standard input/output transport communication pipes:

```python
# if __name__ == "__main__":
#     mcp.run(transport="sse") # ❌ Disabled: Web/Inspector specific routing configuration
if __name__ == "__main__":
    mcp.run() # ✅ Enabled: Reverts server back to 'stdio' stream format for Claude Desktop
```
3. Restart your Claude Desktop app or run your custom `hr_agent.py` loop script to begin querying data safely again.


## 📂 Repository File Structure

```text
umbrella-corp-hr-mcp/
├── .github/
│   └── workflows/
│       └── ci.yml             # Continuous Integration automated build engine
├── prompts/
│   └── claude_desktop.md      # Dual-Pass UI instructions for Claude Desktop
├── src/
│   ├── client/
│   │   └── hr_agent.py        # LangGraph client orchestration application
│   ├── database/
│   │   └── seed_db.py         # Relational database layout seeding engine
│   │   └── hr_database.db
│   └── server/
│       └── hr_mcp_server.py   # FastMCP server + server-side masking engine
├── .env.example               # Configuration parameter placeholder template
├── .gitignore                 # Blocks cache, local environments, and database binaries
├── pyproject.toml             # Modern package build and configuration metadata
└── requirements.txt           # Explicit frozen dependency version manifest
```
