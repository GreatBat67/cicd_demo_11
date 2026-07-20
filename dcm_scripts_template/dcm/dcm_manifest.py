# Generate DCM manifest.yml from branch-based config
from pathlib import Path
import sys
import yaml

sys.dont_write_bytecode = True

# ============================================================
# LOAD CONFIGURATION
# ============================================================

ROOT = Path.cwd().parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import importlib
import config.config as cfg
importlib.reload(cfg)

config = cfg.config
PROJECT_DIR = cfg.PROJECT_DIR
MANIFEST_FILE = cfg.MANIFEST_FILE
LOGS_DIR = cfg.LOGS_DIR

# ============================================================
# YAML DUMPER
# ============================================================

class NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True

# ============================================================
# CONFIG
# ============================================================

BRANCH_DATA = config.branch_data
ROLES = config.roles
ACCOUNT_IDENTIFIER = config.account_identifier
WAREHOUSE = config.warehouse
ADMIN_ROLE = config.admin_role.upper()

# ------------------------------------------------------------
# DYNAMIC DEFAULT TARGET & PROJECT NAME RESOLUTION
# ------------------------------------------------------------
DEFAULT_TARGET = None
DEFAULT_PROJECT_NAME = None

for branch_name, branch_info in BRANCH_DATA.items():
    # Check for various ways the flag might have been written in YAML
    is_def = branch_info.get("is_default")
    is_def_tgt = branch_info.get("is_default_target")
    is_def_true = branch_info.get("is_default_true")
    
    # If any of these evaluate to true in the YAML, use this target as the master
    if str(is_def).lower() == 'true' or str(is_def_tgt).lower() == 'true' or str(is_def_true).lower() == 'true':
        DEFAULT_TARGET = branch_info.get("dcm_target")
        
        # Build the centralized project name based on this default branch (Metadata)
        db = branch_info.get("sf_databases", [""])[0].upper()
        schema = branch_info.get("sf_schemas", ["PUBLIC"])[0].upper()
        dcm_dir = branch_info.get("dcm_dir", "DCM_AUTOMATION").upper()
        DEFAULT_PROJECT_NAME = f"{db}.{schema}.{dcm_dir}"
        
        print(f"--> Found default target flag in branch: {branch_name}")
        break

# Fallback to the first available target if the flag wasn't found
if not DEFAULT_TARGET:
    print("--> WARNING: Default flag not found in YAML. Falling back to the first available branch.")
    first_branch = next(iter(BRANCH_DATA.values()), {})
    DEFAULT_TARGET = first_branch.get("dcm_target")
    db = first_branch.get("sf_databases", [""])[0].upper()
    schema = first_branch.get("sf_schemas", ["PUBLIC"])[0].upper()
    dcm_dir = first_branch.get("dcm_dir", "DCM_AUTOMATION").upper()
    DEFAULT_PROJECT_NAME = f"{db}.{schema}.{dcm_dir}"


MANIFEST_VERSION = 2
PROJECT_TYPE = "DCM_PROJECT"

# ============================================================
# BUILD MANIFEST
# ============================================================

def build_manifest():

    targets = {}
    configurations = {}

    for branch_name, branch in BRANCH_DATA.items():

        databases = branch.get("sf_databases", [])
        schemas = branch.get("sf_schemas", [])
        dcm_target = branch.get("dcm_target")
        branch_roles = branch.get("sf_roles", list(ROLES.keys()))

        if not databases or not dcm_target:
            continue

        database = databases[0].upper()

        # ENSURE THE PROJECT NAME IS IDENTICAL FOR ALL TARGETS AND CONFIGS
        project_name = DEFAULT_PROJECT_NAME

        targets[dcm_target] = {
            "account_identifier": ACCOUNT_IDENTIFIER,
            "project_name": project_name,  # <--- Project name safely kept inside Targets
            "project_owner": ADMIN_ROLE,
            "templating_config": branch_name,
        }

        # Convert roles to a dictionary so Jinja can look up roles by their logical name
        if isinstance(branch_roles, dict):
            roles_dict = {k.upper(): v.upper() for k, v in branch_roles.items()}
        else:
            roles_dict = {r.upper(): r.upper() for r in branch_roles}

       # Check if this branch has the default target flag in your YAML
        is_def = branch.get("is_default")
        is_def_tgt = branch.get("is_default_target")
        is_def_true = branch.get("is_default_true")
        
        # Evaluates to True if any of them are 'true' in your YAML
        is_this_default = str(is_def).lower() == 'true' or str(is_def_tgt).lower() == 'true' or str(is_def_true).lower() == 'true'

        configurations[branch_name] = {
            "environment": branch_name,
            "env_suffix": f"_{branch_name}",
            "database": database,
            "schemas": [s.upper() for s in schemas],
            "project_name": project_name,
            "project_owner": ADMIN_ROLE,
            "roles": roles_dict,
            # EXPORTS YOUR YAML FLAG directly to Jinja
            "is_default_target": is_this_default, 
        }

    return {
        "manifest_version": MANIFEST_VERSION,
        "type": PROJECT_TYPE,
        # REMOVED the root project_name here so DCM validation succeeds
        "default_target": DEFAULT_TARGET,
        "targets": targets,
        "templating": {
            "defaults": {
                "project_owner_role": ADMIN_ROLE,
                "warehouse": WAREHOUSE,
            },
            "configurations": configurations,
        },
    }

# ============================================================
# WRITE MANIFEST
# ============================================================

def write_manifest(manifest):

    with MANIFEST_FILE.open("w", encoding="utf-8") as f:
        yaml.dump(
            manifest,
            f,
            Dumper=NoAliasDumper,
            default_flow_style=False,
            sort_keys=False,
        )

    return MANIFEST_FILE

# ============================================================
# MAIN
# ============================================================

def main():

    manifest = build_manifest()
    manifest_path = write_manifest(manifest)

    print("=" * 60)
    print("Manifest generated successfully.")
    print(f"Output : {manifest_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()