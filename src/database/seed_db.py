import sqlite3
import random
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from faker import Faker

# --- Constants & Configuration ---
DB_PATH = Path(__file__).parent / "hr_database.db"
fake = Faker()
VALID_ROLES = ["employee", "hr", "admin"]

def hash_password(password: str) -> str:
    """Standardized SHA256 hashing with string cleaning."""
    clean_p = str(password).strip()
    return hashlib.sha256(clean_p.encode('utf-8')).hexdigest()

def input_with_validation(prompt: str, valid_options: list = None, default: str = None):
    """Helper to get command line input with optional parameter validation."""
    while True:
        value = input(prompt).strip()
        if not value and default is not None:
            return default
        if valid_options:
            if value.lower() in valid_options:
                return value.lower()
            print(f"Invalid input. Choose one of: {', '.join(valid_options)}")
        else:
            if value:
                return value

def initialize_empty_schemas(conn):
    """Generates structural database tables directly mapping your exact SQL constraints."""
    cursor = conn.cursor()

    print("🧹 Cleaning old tables to avoid layout drift...")
    cursor.execute("DROP TABLE IF EXISTS employee_skills")
    cursor.execute("DROP TABLE IF EXISTS chat_audit_logs")
    cursor.execute("DROP TABLE IF EXISTS employees")
    cursor.execute("DROP TABLE IF EXISTS users")

    print("🏗️  Building database layout schemas with exact PK/FK integrity...")

    # Independent parent table containing authentication details
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'employee' CHECK(role IN ('employee', 'hr', 'admin')),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            question TEXT,
            answer TEXT,
            source_used TEXT,
            node_path TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Dependent child table where user_id is BOTH a Primary Key and a Foreign Key linking to users
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            user_id TEXT PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            email TEXT,
            phone_number TEXT,
            position TEXT,
            department TEXT,
            location TEXT,
            hire_date DATE,
            supervisor_id TEXT,
            salary REAL,
            available_pto INTEGER DEFAULT 15,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (supervisor_id) REFERENCES employees(user_id)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employee_skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            skill TEXT,
            FOREIGN KEY(user_id) REFERENCES employees(user_id) ON DELETE CASCADE
        );
    """)

def generate_and_seed_employees(num_employees: int = 5, manual: bool = False):
    conn = sqlite3.connect(DB_PATH)
    # Enforce SQLite engine runtime verification of our declared FK constraints
    conn.execute("PRAGMA foreign_keys = ON")

    initialize_empty_schemas(conn)
    cursor = conn.cursor()

    print(f"🌱 Seeding {num_employees} employees...")
    existing_ids = []

    for i in range(num_employees):
        # Format matching your target database preferences: user_XXXX
        employee_id = f"user_{random.randint(1000, 9999)}"

        # 🛡️ Supervisor Guard: Must pick from employees that already fully exist in the DB
        supervisor_id = random.choice(existing_ids) if existing_ids else None

        if manual:
            print(f"\n--- Enter employee details ({i+1}/{num_employees}) ---")
            first_name = input_with_validation("First Name: ")
            last_name = input_with_validation("Last Name: ")
            username = input_with_validation("Username: ")
            password = input_with_validation("Password (default: password123): ", default="password123")
            position = input_with_validation("Position: ")
            salary = float(input_with_validation("Salary: "))
            role = input_with_validation(f"Role ({'/'.join(VALID_ROLES)}): ", VALID_ROLES)
            email = input_with_validation("Email (optional): ", default=fake.email())
            phone_number = input_with_validation("Phone number (optional): ", default=fake.phone_number())
            department = input_with_validation("Department (optional): ", default=random.choice(["IT", "HR", "Security"]))

            raw_skills = input_with_validation("Skills (comma separated, optional): ", default="Python, AI")
            skills_list = [s.strip().upper() for s in raw_skills.split(",") if s.strip()]

            location = input_with_validation("Location (optional): ", default=random.choice(["Raccoon City HQ", "Umbrella Europe"]))
            hire_date = input_with_validation(
                "Hire Date (YYYY-MM-DD, optional): ",
                default=(datetime.now() - timedelta(days=random.randint(1, 3000))).strftime("%Y-%m-%d")
            )
        else:
            first_name = fake.first_name()
            last_name = fake.last_name()
            username = f"{first_name.lower()}_{employee_id[5:]}"
            password = "password123"
            position = random.choice(["Software Engineer", "HR Specialist", "Security Officer"])
            salary = round(random.uniform(40000, 120000), 2)
            role = random.choice(VALID_ROLES)
            email = fake.email()
            phone_number = fake.phone_number()
            department = random.choice(["IT", "HR", "Security"])

            skills_list = random.sample(["PYTHON", "SECURITY", "AI"], k=2)
            location = random.choice(["Raccoon City HQ", "Umbrella Europe"])
            hire_date = (datetime.now() - timedelta(days=random.randint(1, 3000))).strftime("%Y-%m-%d")

        p_hash = hash_password(password)

        # 🔒 CONSTRAINT RECONCILIATION STEP 1:
        # Create parent 'users' record first so employees.user_id has a valid target to reference
        cursor.execute("""
            INSERT OR IGNORE INTO users (user_id, username, password_hash, role)
            VALUES (?, ?, ?, ?)
        """, (employee_id, username, p_hash, role))

        # 🔒 CONSTRAINT RECONCILIATION STEP 2:
        # Create the matching 'employees' profile row using the identical employee_id primary key
        cursor.execute("""
            INSERT OR IGNORE INTO employees
            (user_id, first_name, last_name, email, phone_number,
             position, department, location, hire_date,
             supervisor_id, salary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            employee_id, first_name, last_name, email, phone_number,
            position, department, location, hire_date,
            supervisor_id, salary
        ))

        # 🔒 CONSTRAINT RECONCILIATION STEP 3:
        # Link skills rows back to our validated employee identifier primary key
        for skill in skills_list:
            cursor.execute("""
                INSERT INTO employee_skills (user_id, skill)
                VALUES (?, ?)
            """, (employee_id, skill))

        # Track successfully created keys to use safely as supervisors in future loop passes
        existing_ids.append(employee_id)

        sup_log = f"Supervisor: {supervisor_id}" if supervisor_id else "Supervisor: None (Root Executive)"
        print(f"✅ Secure Seed complete: {username} | ID: {employee_id} | {sup_log}")

    conn.commit()
    conn.close()
    print(f"\n🏆 Database generated with complete relational constraint alignment at: {DB_PATH.resolve()}")

if __name__ == "__main__":
    mode = input_with_validation("Seed manually? (yes/no, default: no): ", valid_options=["yes", "no"], default="no")
    manual_mode = True if mode == "yes" else False
    num = int(input_with_validation("Number of employees to seed (default: 5): ", default="5"))
    generate_and_seed_employees(num_employees=num, manual=manual_mode)
