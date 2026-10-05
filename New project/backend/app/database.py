import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy import inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
 
load_dotenv()
 
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
 
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL and all((DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD)):
    DATABASE_URL = (
        f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./tracker.db"
 
engine_options = {}
if DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}
 
engine = create_engine(DATABASE_URL, **engine_options)
 
CANONICAL_USER_ROLES = ("superadmin", "admin", "manager", "tl", "user")
 
 
def migrate_security_schema():
    """Add RBAC columns safely for existing deployments without Alembic yet."""
    with engine.begin() as connection:
        if DATABASE_URL.startswith("postgresql"):
            has_userrole = connection.execute(
                text("SELECT 1 FROM pg_type WHERE typname = 'userrole' LIMIT 1")
            ).fetchone()
 
            if not has_userrole:
                connection.execute(text(
                    "CREATE TYPE userrole AS ENUM ('superadmin', 'admin', 'manager', 'tl', 'user')"
                ))
 
            for role in CANONICAL_USER_ROLES:
                connection.execute(text(
                    f"ALTER TYPE userrole ADD VALUE IF NOT EXISTS '{role}'"
                ))
 
        inspector = inspect(connection)
        if "users" not in inspector.get_table_names():
            return
        columns = {column["name"] for column in inspector.get_columns("users")}
        if "organization_id" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN organization_id INTEGER"))
        if "manager_id" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN manager_id INTEGER"))
        settings_columns = {column["name"] for column in inspector.get_columns("app_settings")} if "app_settings" in inspector.get_table_names() else set()
        if "retention_days" not in settings_columns and settings_columns:
            connection.execute(text("ALTER TABLE app_settings ADD COLUMN retention_days INTEGER NOT NULL DEFAULT 90"))
        if "screenshot_masking_enabled" not in settings_columns and settings_columns:
            connection.execute(text("ALTER TABLE app_settings ADD COLUMN screenshot_masking_enabled BOOLEAN NOT NULL DEFAULT FALSE"))
 
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
 
 
def migrate_schema():
    """Apply small, idempotent schema updates for existing installations."""
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return
 
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "created_by_id" not in user_columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE users ADD COLUMN created_by_id INTEGER "
                    "REFERENCES users(id)"
                )
            )
 
    user_columns = {column["name"] for column in inspect(engine).get_columns("users")}
    if "parent_id" not in user_columns:
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE users ADD COLUMN parent_id INTEGER REFERENCES users(id)")
            )
            if "created_by_id" in user_columns:
                connection.execute(
                    text("UPDATE users SET parent_id = created_by_id WHERE parent_id IS NULL")
                )

    table_names = inspect(engine).get_table_names()
    if "departments" not in table_names:
        return

    department_columns = {
        column["name"] for column in inspect(engine).get_columns("departments")
    }
    if "created_by_id" not in department_columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE departments ADD COLUMN created_by_id INTEGER "
                    "REFERENCES users(id)"
                )
            )

    with engine.begin() as connection:
        inspector = inspect(connection)
        if engine.dialect.name == "postgresql":
            for constraint in inspector.get_unique_constraints("departments"):
                if constraint.get("column_names") == ["name"]:
                    name = engine.dialect.identifier_preparer.quote(constraint["name"])
                    connection.execute(
                        text(f"ALTER TABLE departments DROP CONSTRAINT IF EXISTS {name}")
                    )
        for index in inspector.get_indexes("departments"):
            if index.get("unique") and index.get("column_names") == ["name"]:
                name = engine.dialect.identifier_preparer.quote(index["name"])
                connection.execute(text(f"DROP INDEX IF EXISTS {name}"))
        connection.execute(text("DROP INDEX IF EXISTS uq_departments_name_lower"))
        connection.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_departments_owner_name_lower "
            "ON departments (created_by_id, lower(name)) "
            "WHERE created_by_id IS NOT NULL"
        ))
        connection.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_departments_unowned_name_lower "
            "ON departments (lower(name)) "
            "WHERE created_by_id IS NULL"
        ))
 
 
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
 