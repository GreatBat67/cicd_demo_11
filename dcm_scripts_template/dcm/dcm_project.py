# Generates DCM project creation SQL by picking the default target from config
# Co-authored with CoCo
from pathlib import Path
import sys

sys.dont_write_bytecode = True

ROOT = Path.cwd().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import importlib
import config.config as cfg

importlib.reload(cfg)

config = cfg.config
LOGS_DIR = cfg.LOGS_DIR

# ============================================================
# CONFIG
# ============================================================
BRANCH_DATA = config.branch_data
ADMIN_ROLE = config.admin_role.upper()

# Find the branch where is_default_target is true
target_config = {}
for branch_name, branch_cfg in BRANCH_DATA.items():
    if isinstance(branch_cfg, dict) and branch_cfg.get("is_default_target", False):
        target_config = branch_cfg
        break

if not target_config:
    raise RuntimeError("No branch with is_default_target: true found in project_config.yml")

sf_databases = target_config.get("sf_databases", [])
sf_schemas = target_config.get("sf_schemas", [])
DCM_PROJECT_NAME = target_config.get("dcm_dir", "").upper()

OUTPUT_FILE = LOGS_DIR / "create_dcm_projects.sql"

# ============================================================
# GENERATE SQL
# ============================================================
sql = []
sql.append("-- ====================================================")
sql.append("-- CREATE DCM PROJECTS")
sql.append("-- ====================================================")
sql.append("")
sql.append(f"USE ROLE {ADMIN_ROLE};")
sql.append("")

for db in sf_databases:
    db_upper = db.upper()
    for schema in sf_schemas:
        schema_upper = schema.upper()
        
        
        sql.append(f"USE DATABASE {db_upper};")
        sql.append(f"USE SCHEMA {db_upper}.{schema_upper};")
        sql.append(f"CREATE DCM PROJECT IF NOT EXISTS {db_upper}.{schema_upper}.{DCM_PROJECT_NAME};")
        sql.append("")

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write("\n".join(sql))

print("DCM Project SQL generated successfully.")
print(f"Output: {OUTPUT_FILE}")