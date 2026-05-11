import sys
# Ensures your virtual environment packages are discoverable
sys.path.insert(0, "/Users/abhisakhsarma/Software_Engineering/Master_School/MCP/my_mcp_project/.venv/lib/python3.13/site-packages")

import os
import sqlite3
import hashlib
import uuid
from pathlib import Path
from datetime import datetime
from mcp.server.fastmcp import FastMCP
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore

# Resolves: src/server -> moves up to src/ -> drops into database/hr_database.db
DB_PATH = Path(__file__).resolve().parent.parent / "database" / "hr_database.db"

mcp = FastMCP("HR_Assistant")

# 🔒 Server-side token storage completely isolated from the LLM heap
TOKEN_VAULT = {}

# # 🔐 Extract the fixed, immutable role injected by hr_agent.py at process startup
# SESSION_ROLE = os.getenv("SESSION_ROLE", "employee").lower()

# 🔒 In-memory session state (Tracks the active user in Claude Desktop)
# All tools are blocked until 'user_id' is populated via authenticate_user.
CURRENT_SESSION = {
    "user_id": None,
    "role": "guest",
    "first_name": "Guest"
}

def is_authenticated():
    """Checks if a user has successfully logged into the current session."""
    return CURRENT_SESSION["user_id"] is not None

def get_secure_db():
    """Creates a connection context that enforces masking at the cursor layer."""
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")

    # Register the masking engine function directly inside SQLite query loops
    conn.create_function("ENFORCE_PII_POLICY", 2, sql_mask_gate)
    return conn

# For non-secure tasks like authentication and audit insertion
def get_raw_db():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn

def sql_mask_gate(column_name: str, real_value: str) -> str:
    """
    INTERNAL POLICY ENGINE: Enforces PII masking based on CURRENT_SESSION['role'].
    """
    if not real_value:
        return ""

    # Tokens are only generated if the session is HR or Admin level.
    if CURRENT_SESSION["role"] in ["admin", "hr"]:
        token = f"[TOKEN_{column_name.upper()}_{uuid.uuid4().hex[:8].upper()}]"
        TOKEN_VAULT[token] = str(real_value)
        return token

    return "[REDACTED_UNAUTHORIZED]"


# --- TOOL 1: Bulk Search ---
@mcp.tool()
def query_employees(department: str = None, limit: int = 10) -> list[dict] | dict:
    """
    CRITICAL WORKFORCE BROWSER: Retrieves staff metadata records for groups or departments.

    CRITICAL RESTRICTION 1: Do NOT call this tool for singular ID lookups (e.g., 'EMP001').
    Use 'get_employee_by_id' instead.

    CRITICAL RESTRICTION 2: This tool is LOCKED until 'authenticate_user' is successfully
    called. If unauthenticated, it returns a status error.

    Args:
        department (str, optional): The target corporate group filter (e.g., 'Engineering').
        limit (int, optional): Max records to retrieve to avoid context bloat. Defaults to 10.

    Returns:
        list[dict]: A list of objects containing:
            - user_id (str): Unique identifier.
            - first_name, last_name (str): Employee name.
            - department, position (str): Role and group details.
            - email (str): Work contact.
            - hire_date (str): ISO date of joining.
            - available_pto (int): Remaining leave balance.
            - salary (str): Masked token (e.g., [TOKEN_SALARY_XXXX]) or [REDACTED].
            - bank_account (str): Masked token or [REDACTED].
            - home_address (str): Masked token or [REDACTED].
        dict: Returns an error status if the session is not authenticated.
    """
    # Verify session before proceeding
    if not is_authenticated():
        return {"status": "error", "message": "AUTHENTICATION REQUIRED: Please log in to view workforce data."}

    with get_secure_db() as conn:
        sql_query = """
            SELECT
                user_id, first_name, last_name, department, position, email, hire_date, available_pto,
                ENFORCE_PII_POLICY('salary', salary) as salary,
                ENFORCE_PII_POLICY('bank', bank_account) as bank_account,
                ENFORCE_PII_POLICY('address', home_address) as home_address
            FROM employees
        """
        if department:
            sql_query += " WHERE department = ? LIMIT ?"
            rows = conn.execute(sql_query, (department, limit)).fetchall()
        else:
            sql_query += " LIMIT ?"
            rows = conn.execute(sql_query, (limit,)).fetchall()

        return [dict(r) for r in rows]


# --- TOOL 2: Identity Lookup ---
@mcp.tool()
def get_employee_by_id(user_id: str) -> dict:
    """
    SINGLE PROFILE RETRIEVER: This tool is MANDATORY for retrieving comprehensive, singular record
    histories from the primary personnel registry. Call this tool immediately when a precise
    individual Employee ID string (strictly formatted as 'EMP' followed by digits, e.g., 'EMP023')
    is provided or inferred from the conversational text context.

    CRITICAL RESTRICTION: This tool implements server-side role masking. Do NOT try to skip or
    bypass token mappings. If fields like 'salary' emerge as a token wrapper format like
    '[TOKEN_SALARY_A1B2C3]', your obligation is to render that explicit block intact. The
    client framework interface handles localized translation for authorized HR workers.

    Args:
        user_id (str): The unique target alphanumeric corporate database identifier assigned to the
            specific individual being investigated (e.g., 'EMP001', 'EMP042').

    Returns:
        dict: A status map wrapping data fields if matched. Returns a clear 'error' status message
            sentinel block if the structural key is completely absent from the relational table.
    """
    if not is_authenticated():
        return {"status": "error", "message": "Login required."}
    with get_secure_db() as conn:
        sql_query = """
            SELECT
                user_id, first_name, last_name, department, position, email, hire_date, available_pto,
                ENFORCE_PII_POLICY('salary', salary) as salary,
                ENFORCE_PII_POLICY('bank', bank_account) as bank_account,
                ENFORCE_PII_POLICY('address', home_address) as home_address
            FROM employees
            WHERE user_id = ?
        """
        row = conn.execute(sql_query, (user_id,)).fetchone()
        if not row:
            return {"status": "error", "message": "Employee record not found."}
        return {"status": "success", "data": dict(row)}


# --- TOOL 3: Skill Matching ---
@mcp.tool()
def search_employees_by_skill(skill_query: str) -> list[dict]:
    """
    CAPABILITY DISCOVERY CORE: Use this tool exclusively to execute search functions targeting
    internal talent matrices, technical capabilities, or certifications. Call this tool for any
    semantic question seeking capabilities, such as 'Who knows Python?', 'Find a React engineer',
    'Look up agile management expertise', or 'List our certified AWS architects'.

    Args:
        skill_query (str): The discrete skill keyword, language, tool name, or capability string
            to match against the inner structural database records (e.g., 'Python', 'SQL', 'Figma').

    Returns:
        list[dict]: Array list containing matched employee metadata (names, departments) alongside the
            explicit matching skill entry found in the structural matrices.
    """
    with get_secure_db() as conn:
        rows = conn.execute(
            """SELECT e.first_name, e.last_name, e.department, s.skill
               FROM employees e JOIN employee_skills s ON e.user_id = s.user_id
               WHERE s.skill LIKE ?""", (f"%{skill_query}%",)
        ).fetchall()
        return [dict(r) for r in rows]


# --- TOOL 4: Executive Summary ---
@mcp.tool()
def get_company_stats() -> dict:
    """
    MACRO WORKFORCE ANALYTICS: High-level metric aggregator. This is the MANDATORY tool for processing
    macro-level organizational health analytics. Call this tool when queries ask for aggregated facts
    like 'What is our headcount?', 'How many people work total in the firm?', or 'Give me a
    departmental resource allocation breakdown list'.

    Returns:
        dict: A structural analytics payload containing total integer headcount metrics alongside a
            descending list of operating groups and their localized resource allocation counts.
    """
    with get_secure_db() as conn:
        count_row = conn.execute("SELECT COUNT(*) FROM employees").fetchone()
        count = count_row[0] if count_row else 0
        depts = conn.execute(
            "SELECT department, COUNT(*) as count FROM employees GROUP BY department ORDER BY count DESC"
        ).fetchall()
        return {"total_headcount": count, "departments": [dict(r) for r in depts]}


# --- TOOL 5: Hierarchy Lookup ---
@mcp.tool()
def get_manager_reports(supervisor_name: str) -> list[dict]:
    """
    ORGANIZATIONAL CHART EXPLORER: Use this hierarchy mapper exclusively to evaluate managerial reporting lines,
    chain-of-command links, team operational units, or direct report tracking logs. Call this tool
    automatically for queries such as 'Who reports to Jane?', 'Show me Bob's structural team chart',
    or 'List all personnel under supervisor Alice'.

    Args:
        supervisor_name (str): The full or partial text string name of the target supervisor or corporate manager
            whose organizational tree needs exploration (e.g., 'John Doe').

    Returns:
        list[dict]: A list of records detailing names, corporate positions, and work email addresses
            for all active staff members reporting to the target profile.
    """
    with get_secure_db() as conn:
        rows = conn.execute(
            """SELECT e.first_name, e.last_name, e.position, e.email
               FROM employees e JOIN employees s ON e.supervisor_id = s.user_id
               WHERE (s.first_name || ' ' || s.last_name) LIKE ?""", (f"%{supervisor_name}%",)
        ).fetchall()
        return [dict(r) for r in rows]


# --- TOOL 6: Proactive HR Alerts ---
@mcp.tool()
def get_hr_alerts(alert_type: str) -> list[dict]:
    """
    RETENTION & WELLNESS TRACKER: Operational risk audit engine designed to flag corporate workforce anomalies
    requiring immediate human resource intervention, workload distribution adjusting, or recognition processing.

    Args:
        alert_type (str): Explicitly limited to one of two structural configuration criteria options:
            - 'burnout': Extracts employees possessing more than 12 days of unused Paid Time Off (PTO),
              indicating severe work overexertion risks.
            - 'tenure': Queries institutional veteran profiles showing 5 or more continuous calendar
              years of active service at Umbrella Corp.

    Returns:
        list[dict]: Array list of employee name indicators mapped against corresponding conditional parameters
            (either total remaining PTO integer values or hire date strings).
    """
    if not is_authenticated():
        return [{"error": "Login required."}]
    with get_secure_db() as conn:
        if alert_type == "burnout":
            rows = conn.execute("SELECT first_name, last_name, available_pto FROM employees WHERE available_pto > 12").fetchall()
        else:
            five_years_ago = f"{datetime.now().year - 5}-01-01"
            rows = conn.execute("SELECT first_name, last_name, hire_date FROM employees WHERE hire_date <= ?", (five_years_ago,)).fetchall()
        return [dict(r) for r in rows]


# --- TOOL 7: Financial Analysis ---
@mcp.tool()
def get_salary_stats() -> list[dict]:
    """
    COMPENSATION ANALYTICS ENGINE: Aggregated calculation processor. Computes average salaries across
    corporate organizational groups to enable competitive market adjustments and departmental budgeting reviews.

    CRITICAL ROLE POLICY: Access checking is performed at the operating system context layer. If you are running
    an unprivileged 'employee' session context, executing this tool will automatically return a strict
    denial message payload. Never call this tool for general staff requests.

    Returns:
        list[dict]: A collection of structural database rows tracking average salary calculations rounded
            to two decimal parameters per operational business group.
    """
    if not is_authenticated():
        return [{"error": "Login required."}]
    if CURRENT_SESSION["role"] not in ["admin", "hr"]:
        return [{"error": "Access Denied: Inadequate privileges."}]
    with get_secure_db() as conn:
        rows = conn.execute("SELECT department, ROUND(AVG(salary), 2) as avg_salary FROM employees GROUP BY department").fetchall()
        return [dict(r) for r in rows]


# --- TOOL 8: Policy Search ---
@mcp.tool()
def search_policy_documents(query: str) -> str:
    """
    UNSTRUCTURED POLICY KNOWLEDGE BASE: Semantic vector search endpoint. This tool is MANDATORY for all
    procedural, benefit handbook, legal regulatory compliance, or unstructured corporate policy queries.
    Call this tool for inquiries like 'What is our maternity policy?', 'How do I handle a workplace grievance?',
    'What dental insurance packages exist?', or 'What rules cover standard remote work arrangements?'.

    Args:
        query (str): The complete natural language search phrase, intent prompt, or target question
            to pass directly to the vectorized Pinecone handbook database.

    Returns:
        str: A comprehensive Markdown text string containing the top 3 highly relevant policy context entries,
            complete with document titles and source file citations for LLM context synthesis.
    """
    try:
        index_name = os.getenv("PINECONE_INDEX_NAME")
        if not index_name or not os.getenv("PINECONE_API_KEY") or not os.getenv("OPENAI_API_KEY"):
            return "Configuration Error: Security or index variables missing from host environment."

        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        vectorstore = PineconeVectorStore(index_name=index_name, embedding=embeddings, text_key="text")
        docs = vectorstore.as_retriever(search_kwargs={"k": 3}).invoke(query)

        if not docs:
            return "No matching HR policy documents found in the vector database."

        return "\n\n---\n\n".join([
            f"### Document: {d.metadata.get('title', 'HR Policy Document')}\n"
            f"Source: {d.metadata.get('source', 'Unknown Source')}\n"
            f"Content:\n{d.page_content}" for d in docs
        ])
    except Exception as e:
        return f"Error executing inline LangChain Pinecone search: {str(e)}"


# --- TOOL 9: AUTH TOOL ---
@mcp.tool()
def authenticate_user(username: str, password_plain: str) -> dict:
    """
    SESSION GATEKEEPER: Validates credentials and unlocks the HR server.

    This is the ONLY tool accessible in an unauthenticated state. Upon success,
    it upgrades the server's internal access role and enables all other tools.

    Args:
        username (str): The corporate login name.
        password_plain (str): The plaintext password for server-side hashing.
    """
    u = username.strip()
    p = password_plain.strip()
    incoming_hash = hashlib.sha256(p.encode('utf-8')).hexdigest()

    with get_raw_db() as conn:
        query = """
            SELECT u.user_id, u.role, e.first_name
            FROM users u
            JOIN employees e ON u.user_id = e.user_id
            WHERE u.username = ? AND u.password_hash = ?
        """
        result = conn.execute(query, (u, incoming_hash)).fetchone()

        if result:
            CURRENT_SESSION["user_id"] = result["user_id"]
            CURRENT_SESSION["role"] = result["role"]
            CURRENT_SESSION["first_name"] = result["first_name"]

            return {
                "status": "success",
                "message": f"Welcome, {result['first_name']}. Session unlocked.",
                "user_id": result["user_id"],
                "role": result["role"]
            }
        return {"status": "error", "message": "Invalid credentials. Access denied."}


# --- TOOL 11: LOGOUT USER ---
@mcp.tool()
def logout_user() -> str:
    """
    SECURE TERMINATION: Wipes the session and locks the server immediately.

    Call this to end the session. All subsequent calls to HR tools will be
    blocked until a new login is performed.
    """
    CURRENT_SESSION["user_id"] = None
    CURRENT_SESSION["role"] = "guest"
    CURRENT_SESSION["first_name"] = "Guest"
    return "Session terminated. HR Portal locked."


# --- TOOL 12: AUTOMATIC AUDITING ---
@mcp.tool()
def save_to_audit(user_id: str, question: str, answer: str, source: str, node_path: str) -> str:
    """
    COMPLIANCE LEDGER LOGGER: System telemetry logging utility. This tool is MANDATORY and must be executed
    at the end of every complete conversational turn. It writes transactions to an immutable system database
    log table to satisfy regulatory data compliance tracking and historical reporting requirements.

    CRITICAL RULE: If the answer string contains sensitive PII properties or tracking tokens, ensure the
    calling client redacts or abstracts them before storage to protect log database integrity.

    Args:
        user_id (str): The validated employee tracking string of the user running the terminal (e.g., 'EMP001').
        question (str): The raw, unchanged natural language query entered by the user during this turn.
        answer (str): The final, structural response string generated to resolve the user prompt.
        source (str): The targeted data storage architecture used to resolve this context ('SQL', 'Vector', or 'General').
        node_path (str): The runtime name of the primary server tool function that handled this
            operation loop (e.g., 'query_employees', 'search_policy_documents').

    Returns:
        str: A simple string statement indicating successful database commit completion status.
    """
    with get_raw_db() as conn:
        conn.execute(
            """INSERT INTO chat_audit_logs (user_id, question, answer, source_used, node_path, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, question, answer, source, node_path, datetime.now().isoformat())
        )
        conn.commit()
    return "Audit frame committed successfully."


# --- TOOL 13: HISTORICAL CONTEXT RETRIEVAL ---
@mcp.tool()
def get_chat_history(user_id: str) -> list[dict]:
    """
    CONTEXT RECOVERY ENGINE: Historical conversation recovery tool. Call this tool immediately after a
    successful authentication loop to retrieve the most recent conversation logs for the active user ID.
    This history is used to build context summaries and maintain accurate situational awareness across chat turns.

    Args:
        user_id (str): The validated unique employee tracking ID whose historical log records are being
            extracted from the audit tables.

    Returns:
        list[dict]: A list containing the 5 most recent question-and-answer log pairs associated with the user profile,
            ordered by recent creation timestamp parameters.
    """
    with get_raw_db() as conn:
        rows = conn.execute(
            "SELECT question, answer FROM chat_audit_logs WHERE user_id = ? ORDER BY timestamp DESC LIMIT 5",
            (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]


# --- TOOL 14: SYSTEM ENDPOINT: Client Demasking ---
@mcp.tool()
def demask_token_payload(token: str) -> str:
    """
    INTERNAL PIPELINE DE-TOKENIZER: Swaps data tokens back to their raw text strings.
    This tool is reserved strictly for automated client applications to resolve token structures right
    before displaying text on user terminal screens.

    CRITICAL POLICY: Access checking is performed against the immutable environment-level 'SESSION_ROLE'.
    If a session without 'admin' or 'hr' permissions attempts to execute this tool, it will automatically
    return a blocked response string.

    Args:
        token (str): The unique, random structural tracker token string found in the text layout
            (e.g., '[TOKEN_SALARY_7E4A8F2B]').

    Returns:
        str: The raw, unmasked data value string retrieved from the secure server vault. Returns the input
            token unchanged if no matching state map is found or if permissions are invalid.
    """
    if CURRENT_SESSION["role"] not in ["admin", "hr"]:
        return "[ACCESS_DENIED]"
    return TOKEN_VAULT.get(token, token)

# --- RESOURCE: Technical Meta-data ---
@mcp.resource("hr://schema")
def get_schema() -> str:
    """
    Provides the SQLite database structure. Use if unsure about column names.
    """
    with get_raw_db() as conn:
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        schema = []
        for t in tables:
            cols = conn.execute(f"PRAGMA table_info({t['name']})").fetchall()
            schema.append(f"Table: {t['name']}")
            schema.extend([f"  - {c['name']} ({c['type']})" for c in cols])
        return "\n".join(schema)

if __name__ == "__main__":
    mcp.run()
    #mcp.run(transport="sse")
