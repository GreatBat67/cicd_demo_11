
from pathlib import Path
import sys


sys.dont_write_bytecode = True

# ============================================================
# LOAD CONFIGURATION
# ============================================================

ROOT = Path.cwd().parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.config import config

# ============================================================
# CONFIG
# ============================================================

PROJECT = config.project
PROJECT_NAME = PROJECT["name"]

DATABASES = config.databases
SCHEMAS = config.schemas
ROLES = config.roles
DCM_PROJECT = config.dcm_project
PROJECT_OWNER_ROLE = DCM_PROJECT["owner_role"]
PROJECT_SCHEMA = DCM_PROJECT["schema"]

# ============================================================
# DYNAMIC GRANT DISCOVERY
# ============================================================

from snowflake.snowpark.context import get_active_session

session = get_active_session()

# ---------- Purely rule-based plural/singular conversion ----------


def _pluralize(singular):
    """Convert singular object type to plural form using English rules."""
    words = singular.split()
    last = words[-1]
    if last.endswith("Y") and last[-2:] not in ("AY", "EY", "OY", "UY"):
        words[-1] = last[:-1] + "IES"
    elif last.endswith(("S", "X", "Z", "SH", "CH")):
        words[-1] = last + "ES"
    else:
        words[-1] = last + "S"
    return " ".join(words)


def _singularize(plural):
    """Convert plural object type to singular form using English rules."""
    words = plural.split()
    last = words[-1]
    if last.endswith("IES") and len(last) > 4 and last[-4] not in "AEIOU":
        words[-1] = last[:-3] + "Y"
    elif last.endswith("ES") and (
        last[:-2].endswith(("S", "X", "Z", "SH", "CH"))
    ):
        words[-1] = last[:-2]
    elif last.endswith("S") and not last.endswith("SS"):
        words[-1] = last[:-1]
    return " ".join(words)


# ============================================================
# DISCOVER OBJECT TYPES FROM ALL CONFIGURED SCHEMAS
# ============================================================

reference_db = DATABASES[0]["name"]

print("\nDiscovering object types from Snowflake...")


def _discover_info_schema_object_types(database, schema):
    """
    Dynamically discover additional object types by querying INFORMATION_SCHEMA views.
    Tries SHOW <view_name> IN SCHEMA for each view found - no hardcoded exclusion list.
    """
    additional_types = set()
    try:
        views = session.sql(
            f"SHOW VIEWS IN SCHEMA {database}.INFORMATION_SCHEMA"
        ).collect()

        fqn = f"{database}.{schema}"
        for row in views:
            data = row.as_dict(recursive=True)
            view_name = data.get("name", "").upper()
            if not view_name:
                continue
            # Try running SHOW <view_name> IN SCHEMA; if it works and has
            # results, this view_name is a valid plural object type.
            try:
                results = session.sql(
                    f"SHOW {view_name} IN SCHEMA {fqn}"
                ).collect()
                if results:
                    singular = _singularize(view_name)
                    additional_types.add(singular)
            except Exception:
                # Not a valid SHOW command for this view - skip silently
                pass
    except Exception as e:
        print(f"  Info: Could not query INFORMATION_SCHEMA views: {e}")

    return additional_types


def discover_object_types_in_schema(database, schema):
    """
    Discover all object types that exist in a schema - fully dynamic.
    Uses SHOW OBJECTS + INFORMATION_SCHEMA view probing (zero hardcoded lists).

    Returns:
        dict: {singular_object_type: plural_object_type}
    """
    object_types = set()
    fqn = f"{database}.{schema}"

    # Method 1: SHOW OBJECTS captures tables, views, and many other types
    try:
        results = session.sql(
            f"SHOW OBJECTS IN SCHEMA {fqn}"
        ).collect()

        print(f"\nSchema: {fqn}")

        if not results:
            print("  No objects found via SHOW OBJECTS.")
        else:
            for row in results:
                data = row.as_dict(recursive=True)
                object_name = data.get("name", "<UNKNOWN>")
                object_type = data.get("kind", "<UNKNOWN>")
                print(f"  {object_name:<35} {object_type}")
                if object_type:
                    object_types.add(object_type.upper())

    except Exception as e:
        print(f"  Warning: Could not discover objects in {fqn}: {e}")

    # Method 2: Dynamically probe INFORMATION_SCHEMA views
    additional = _discover_info_schema_object_types(database, schema)
    if additional:
        print(f"  Additional types discovered: {', '.join(sorted(additional))}")
    object_types.update(additional)

    return {
        obj_type: _pluralize(obj_type)
        for obj_type in sorted(object_types)
    }


# ------------------------------------------------------------
# Discover object types across all configured schemas
# ------------------------------------------------------------

OBJECT_TYPE_PLURAL_MAP = {}

for schema in SCHEMAS:

    discovered = discover_object_types_in_schema(
        reference_db,
        schema
    )

    OBJECT_TYPE_PLURAL_MAP.update(discovered)

    print(
        f"  Object types in {schema}: "
        f"{', '.join(sorted(discovered.keys())) if discovered else 'None'}"
    )

# ------------------------------------------------------------
# Fallback: if nothing discovered, query account-level object types
# ------------------------------------------------------------

if not OBJECT_TYPE_PLURAL_MAP:
    print("\nWarning: No object types discovered via schema probing.")
    print("  Falling back to SHOW OBJECTS IN DATABASE...")
    try:
        results = session.sql(
            f"SHOW OBJECTS IN DATABASE {reference_db}"
        ).collect()
        for row in results:
            data = row.as_dict(recursive=True)
            kind = data.get("kind", "")
            if kind:
                k = kind.upper()
                OBJECT_TYPE_PLURAL_MAP[k] = _pluralize(k)
    except Exception as e:
        print(f"  Fallback also failed: {e}")
        print("  Using minimal dynamic discovery from INFORMATION_SCHEMA...")
        try:
            results = session.sql(
                f"SHOW VIEWS IN SCHEMA {reference_db}.INFORMATION_SCHEMA"
            ).collect()
            for row in results:
                data = row.as_dict(recursive=True)
                view_name = data.get("name", "").upper()
                if view_name:
                    singular = _singularize(view_name)
                    OBJECT_TYPE_PLURAL_MAP[singular] = view_name
        except Exception:
            pass

print("\n============================================================")
print("Discovered Object Types Across All Schemas")
print("============================================================")

for obj_type in sorted(OBJECT_TYPE_PLURAL_MAP.keys()):
    print(f"  - {obj_type}")

print("============================================================")

def discover_role_grants(role_name):
    """
    Discover schema CREATE privileges and object privileges granted to a role.
    """
    schema_create_grants = set()
    object_privileges = {}

    try:
        results = session.sql(
            f"SHOW GRANTS TO ROLE {role_name}"
        ).collect()

        for row in results:
            data = row.as_dict(recursive=True)

            privilege = data["privilege"]
            granted_on = data["granted_on"]

            if granted_on == "SCHEMA" and privilege.startswith("CREATE"):
                schema_create_grants.add(privilege)

            if granted_on in OBJECT_TYPE_PLURAL_MAP:
                object_privileges.setdefault(granted_on, set()).add(privilege)

    except Exception as e:
        print(f"Warning: Could not run SHOW GRANTS TO ROLE {role_name}: {e}")

    return (
        sorted(schema_create_grants),
        {k: sorted(v) for k, v in object_privileges.items()},
    )


def discover_future_grants_for_role(database, schema, role_name):
    """
    Discover future grants for a role in a schema.
    """
    future_grants = {}

    try:
        fqn = f"{database}.{schema}"

        results = session.sql(
            f"SHOW FUTURE GRANTS IN SCHEMA {fqn}"
        ).collect()

        for row in results:
            data = row.as_dict(recursive=True)

            grantee = (
                data.get("grantee_name")
                or data.get("grantee")
                or ""
            )

            if grantee.upper() != role_name.upper():
                continue

            grant_on = data["grant_on"]
            privilege = data["privilege"]

            future_grants.setdefault(grant_on, set()).add(privilege)

    except Exception as e:
        print(
            f"Warning: Could not run SHOW FUTURE GRANTS IN SCHEMA {database}.{schema}: {e}"
        )

    return {
        k: sorted(v)
        for k, v in future_grants.items()
    }


# ============================================================
# DISCOVER GRANTS PER ROLE
# ============================================================

ROLE_GRANTS = {}

for role_name in ROLES.keys():

    print(f"\n{'=' * 60}")
    print(f"Role : {role_name}")
    print(f"{'=' * 60}")

    schema_create, obj_privs = discover_role_grants(role_name)

    future = {}

    # Discover future grants from every configured schema
    for schema in SCHEMAS:

        schema_future = discover_future_grants_for_role(
            reference_db,
            schema,
            role_name
        )

        for obj_type, privileges in schema_future.items():
            future.setdefault(obj_type, set()).update(privileges)

    future = {
        k: sorted(v)
        for k, v in future.items()
    }

    # Fallback: derive from discovered object types instead of hardcoding
    if not schema_create and not future:
        print(f"Warning: No grants discovered for {role_name}. Deriving from discovered types.")

        # Build CREATE privileges for each discovered object type
        schema_create = sorted(
            f"CREATE {obj_type}" for obj_type in OBJECT_TYPE_PLURAL_MAP.keys()
        )

        # Determine valid privileges per object type dynamically
        future = {}
        for obj_type, plural in OBJECT_TYPE_PLURAL_MAP.items():
            try:
                # SHOW GRANTS ON <plural> returns grantable privileges
                privs_result = session.sql(
                    f"SHOW GRANTS ON {obj_type} IN SCHEMA {reference_db}.{SCHEMAS[0]}"
                ).collect()
                if privs_result:
                    discovered_privs = set()
                    for r in privs_result:
                        d = r.as_dict(recursive=True)
                        p = d.get("privilege", "")
                        if p and p not in ("OWNERSHIP",):
                            discovered_privs.add(p)
                    if discovered_privs:
                        future[obj_type] = sorted(discovered_privs)
                        continue
            except Exception:
                pass
            # Default: SELECT for types whose plural ends in TABLES/VIEWS, USAGE otherwise
            if "TABLE" in obj_type or "VIEW" in obj_type:
                future[obj_type] = ["SELECT"]
            else:
                future[obj_type] = ["USAGE"]

    ROLE_GRANTS[role_name] = {
        "schema_create_grants": schema_create,
        "object_privileges": obj_privs,
        "future_grants": future,
    }

    print("\nSchema CREATE Privileges")
    print("------------------------")
    print(schema_create)

    print("\nObject Privileges")
    print("-----------------")
    print(obj_privs)

    print("\nFuture Grants")
    print("-------------")
    print(future)
# ============================================================
# BUILD ENV CONFIG
# ============================================================

ENV_CONFIG = {}

for db in DATABASES:
    ENV_CONFIG[db["environment"]] = {
        "database": db["name"],
        "schemas": SCHEMAS,
        "roles": {role: role for role in ROLES.keys()},
    }

# ============================================================
# LOCATE PROJECT DIRECTORY
# ============================================================

PROJECT_NAME = config.project["name"].lower()

current = Path.cwd().resolve()

project_dir = None

for parent in [current] + list(current.parents):

    for child in parent.iterdir():

        if (
            child.is_dir()
            and child.name.lower() == PROJECT_NAME
        ):
            project_dir = child.resolve()
            break

    if project_dir:
        break

if project_dir is None:
    raise RuntimeError(
        f"Could not locate project directory '{PROJECT_NAME}'."
    )

MACROS_DIR = project_dir / "sources" / "macros"
DEFINITION_DIR = project_dir / "sources" / "definitions"

MACROS_DIR.mkdir(parents=True, exist_ok=True)
DEFINITION_DIR.mkdir(parents=True, exist_ok=True)

print(f"\nProject directory    : {project_dir}")
print(f"Macros directory     : {MACROS_DIR}")
print(f"Definition directory : {DEFINITION_DIR}")

# ============================================================
# GENERATE MACRO (per-role differentiated grants)
# ============================================================
def generate_grants_macro():

    lines = []

    lines.append(
        "{% macro create_dcm_project(database, schemas, roles, project_owner_role) %}"
    )
    lines.append("")

    # Generate a separate block for each role with its discovered privileges
    for role_name, grants in ROLE_GRANTS.items():
        schema_create = grants["schema_create_grants"]
        future = grants["future_grants"]

        lines.append(f"-- Grants for role: {role_name}")
        lines.append("")

        # Database usage
        lines.append(
            f"GRANT USAGE ON DATABASE {{{{ database }}}} TO ROLE {role_name};"
        )
        lines.append("")

        # Per-schema grants
        lines.append("{% for schema in schemas %}")
        lines.append("{% set full_schema = database ~ '.' ~ schema %}")
        lines.append("")

        # Schema usage
        lines.append(
            f"GRANT USAGE ON SCHEMA {{{{ full_schema }}}} TO ROLE {role_name};"
        )
        lines.append("")

        # Schema CREATE privileges
        for privilege in schema_create:
            lines.append(
                f"GRANT {privilege} ON SCHEMA {{{{ full_schema }}}} TO ROLE {role_name};"
            )

        if schema_create:
            lines.append("")

        # Object-level grants on ALL and FUTURE
        for obj_type, privileges in future.items():
            plural = OBJECT_TYPE_PLURAL_MAP.get(obj_type, _pluralize(obj_type))
            for priv in privileges:
                lines.append(
                    f"GRANT {priv} ON ALL {plural} IN SCHEMA {{{{ full_schema }}}} TO ROLE {role_name};"
                )
                lines.append(
                    f"GRANT {priv} ON FUTURE {plural} IN SCHEMA {{{{ full_schema }}}} TO ROLE {role_name};"
                )

        lines.append("")
        lines.append("{% endfor %}")
        lines.append("")

    # Role hierarchy
    lines.append("{% if roles|length > 1 %}")
    lines.append("{% for i in range(roles|length - 1) %}")
    lines.append(
        "GRANT ROLE {{ roles[i] }} TO ROLE {{ roles[i + 1] }};"
    )
    lines.append("{% endfor %}")

    lines.append("{% if roles[-1] != project_owner_role %}")
    lines.append(
        "GRANT ROLE {{ roles[-1] }} TO ROLE {{ project_owner_role }};"
    )
    lines.append("{% endif %}")

    lines.append("{% endif %}")

    lines.append("")
    lines.append("{% endmacro %}")

    return "\n".join(lines)

# ============================================================
# DEMO FILE
# ============================================================

def generate_demo():

    return """
-- Execute RBAC Macro

{{ create_dcm_project(
    database,
    schemas,
    roles,
    project_owner_role
) }}
"""

# ============================================================
# WRITE FILES
# ============================================================

(MACROS_DIR / "grants_macro.sql").write_text(
    generate_grants_macro(),
    encoding="utf-8",
)

(DEFINITION_DIR / "jinja_demo.sql").write_text(
    generate_demo(),
    encoding="utf-8",
)

print("=" * 60)
print("Files generated successfully.")
print(f"Macro file      : {MACROS_DIR / 'grants_macro.sql'}")
print(f"Definition file : {DEFINITION_DIR / 'jinja_demo.sql'}")
print("=" * 60)
