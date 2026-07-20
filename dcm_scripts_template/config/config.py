from pathlib import Path
import yaml


class ConfigLoader:
    """Load configuration from project_config.yml."""

    def __init__(self, config_file="project_config.yml"):

        # ----------------------------------------------------
        # Locate config directory
        # ----------------------------------------------------

        try:
            base_dir = Path(__file__).resolve().parent

        except NameError:
            current = Path.cwd().resolve()

            base_dir = None

            for parent in [current] + list(current.parents):

                candidate = parent / "config"

                if (
                    candidate.exists()
                    and (candidate / config_file).exists()
                ):
                    base_dir = candidate
                    break

            if base_dir is None:
                raise RuntimeError(
                    f"Could not locate '{config_file}'."
                )

        self.base_dir = base_dir
        self.config_file = base_dir / config_file

        # ----------------------------------------------------
        # Read configuration
        # ----------------------------------------------------

        if not self.config_file.exists():
            raise FileNotFoundError(self.config_file)

        with self.config_file.open(
            "r",
            encoding="utf-8",
        ) as f:

            self._config = yaml.safe_load(f) or {}

    # ========================================================
    # Properties
    # ========================================================

    @property
    def snowflake_global(self):
        return self._config.get("snowflake_global", {})

    @property
    def roles(self):
        return self._config.get("roles", {})

    @property
    def branch_data(self):
        return self._config.get("branch_data", {})

    # ========================================================
    # Derived helpers
    # ========================================================

    @property
    def account_identifier(self):
        return self.snowflake_global.get("account_identifier")

    @property
    def admin_role(self):
        return self.snowflake_global.get("admin_role")

    @property
    def warehouse(self):
        return self.snowflake_global.get("warehouse")

    def get_branch(self, branch_name):
        return self.branch_data.get(branch_name, {})

    @property
    def all_databases(self) -> list:
        """Dynamically aggregates all unique databases from every single branch 
        and project target block configured within project_config.yml."""
        dbs = set()
    
    # Iterate through all configured blocks under branch_data dynamically
        for branch_name, branch in self.branch_data.items():
            if isinstance(branch, dict):
                 for db in branch.get("sf_databases", []):
                     dbs.add(db.upper())
                
        return sorted(list(dbs))

    @property
    def all_schemas(self):
        """All unique schemas across all branches."""
        schemas = []
        for branch_name, branch in self.branch_data.items():
            for schema in branch.get("sf_schemas", []):
                if schema not in schemas:
                    schemas.append(schema)
        return schemas

    @property
    def environments(self):
        """List of branch/environment names."""
        return list(self.branch_data.keys())

    @property
    def dcm_project_name(self):
        """DCM project directory name (common across branches)."""
        for branch in self.branch_data.values():
            if "dcm_dir" in branch:
                return branch["dcm_dir"]
        return None

    @property
    def dbt_dir(self):
        """dbt directory path (common across branches)."""
        for branch in self.branch_data.values():
            if "dbt_dir" in branch:
                return branch["dbt_dir"]
        return None


# ============================================================
# LOAD CONFIG
# ============================================================

config = ConfigLoader()

# Snowflake global
ACCOUNT_IDENTIFIER = config.account_identifier
ADMIN_ROLE = config.admin_role
WAREHOUSE = config.warehouse

# Roles
ROLES = config.roles

# Branch data
BRANCH_DATA = config.branch_data

# Derived
ALL_DATABASES = config.all_databases
ALL_SCHEMAS = config.all_schemas
DCM_PROJECT_NAME = config.dcm_project_name
DBT_DIR = config.dbt_dir

# ============================================================
# DIRECTORY STRUCTURE
# ============================================================

SCRIPTS_DIR = config.base_dir.parent

# logs/ (inside scripts)
LOGS_DIR = SCRIPTS_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# workspace/ (parent of scripts)
WORKSPACE_DIR = SCRIPTS_DIR.parent

# ------------------------------------------------------------
# Locate DCM project
# ------------------------------------------------------------

PROJECT_DIR = None

if DCM_PROJECT_NAME:
    for child in WORKSPACE_DIR.iterdir():
        if (
            child.is_dir()
            and child.name.lower() == DCM_PROJECT_NAME.lower()
        ):
            PROJECT_DIR = child.resolve()
            break

MANIFEST_FILE = PROJECT_DIR / "manifest.yml" if PROJECT_DIR else None

MACROS_DIR = None
DEFINITIONS_DIR = None

if PROJECT_DIR:
    MACROS_DIR = PROJECT_DIR / "sources" / "macros"
    MACROS_DIR.mkdir(parents=True, exist_ok=True)

    DEFINITIONS_DIR = PROJECT_DIR / "sources" / "definitions"
    DEFINITIONS_DIR.mkdir(parents=True, exist_ok=True)

# dbt project directory
DBT_PROJECT_DIR = None
if DBT_DIR:
    DBT_PROJECT_DIR = WORKSPACE_DIR / Path(DBT_DIR).name
    DBT_PROJECT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# DEBUG
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("CONFIGURATION")
    print("=" * 60)

    print("Config File      :", config.config_file)
    print("Account          :", ACCOUNT_IDENTIFIER)
    print("Admin Role       :", ADMIN_ROLE)
    print("Warehouse        :", WAREHOUSE)
    print("Scripts Dir      :", SCRIPTS_DIR)
    print("Workspace Dir    :", WORKSPACE_DIR)
    print("Logs Dir         :", LOGS_DIR)
    print("Project Dir      :", PROJECT_DIR)
    print("Manifest         :", MANIFEST_FILE)
    print("Macros           :", MACROS_DIR)
    print("Definitions      :", DEFINITIONS_DIR)
    print("dbt              :", DBT_PROJECT_DIR)

    print("\nBranches:")
    for branch_name, branch in BRANCH_DATA.items():
        print(f"  {branch_name}:")
        print(f"    databases: {branch.get('sf_databases')}")
        print(f"    schemas:   {branch.get('sf_schemas')}")
        print(f"    dcm_target: {branch.get('dcm_target')}")

    print("\nRoles:")
    for role, policy in ROLES.items():
        print(f"  {role}: {policy}")

    print("=" * 60)
