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

## 🚀 Installation & Local Verification

1. Clone this repository and establish your virtual environment variables:
   ```bash
   git clone github.com
   cd umbrella-corp-hr-mcp
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -e .
   ```

2. Create your `.env` configuration mapping based on `.env.example`:
   ```bash
   cp .env.example .env
   # Populate with your OpenAI, Pinecone, and configuration parameter items
   ```

3. Seed the relational datastore (creates user structures, links supervisors, and hashes passwords safely):
   ```bash
   python src/database/seed_db.py
   ```

4. Run the interactive LangGraph pipeline console framework application:
   ```bash
   python src/client/hr_agent.py
   ```
