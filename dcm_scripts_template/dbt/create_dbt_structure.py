import os
import yaml
import sys
from pathlib import Path
sys.dont_write_bytecode = True

# scripts directory
SCRIPTS_DIR = Path.cwd().parent

# project root (parent of scripts)
ROOT_DIR = SCRIPTS_DIR.parent
def create_dbt_structure(base_dir):
    """Creates a standard dbt project structure."""

    dirs = [
        base_dir,
        os.path.join(base_dir, "analyses"),
        os.path.join(base_dir, "logs"),
        os.path.join(base_dir, "macros"),
        os.path.join(base_dir, "models"),
        os.path.join(base_dir, "seeds"),
        os.path.join(base_dir, "snapshots"),
        os.path.join(base_dir, "target"),
        os.path.join(base_dir, "tests"),
    ]

    for d in dirs:
        os.makedirs(d, exist_ok=True)

    # -------------------------
    # dbt_project.yml
    # -------------------------
    dbt_project = os.path.join(base_dir, "dbt_project.yml")
    if not os.path.exists(dbt_project):
        with open(dbt_project, "w") as f:
            f.write(f"""name: "{Path(base_dir).name}"
version: "1.0.0"
config-version: 2

profile: "{Path(base_dir).name}"

model-paths: ["models"]
analysis-paths: ["analyses"]
test-paths: ["tests"]
seed-paths: ["seeds"]
macro-paths: ["macros"]
snapshot-paths: ["snapshots"]

target-path: "target"
clean-targets:
  - "target"
  - "dbt_packages"

models:
  {Path(base_dir).name}:
    +materialized: view
""")

    # -------------------------
    # packages.yml
    # -------------------------
    packages = os.path.join(base_dir, "packages.yml")
    if not os.path.exists(packages):
        with open(packages, "w") as f:
            f.write("# Add dbt packages here\n")

    # -------------------------
    # profiles.yml
    # -------------------------
    profiles = os.path.join(base_dir, "profiles.yml")
    if not os.path.exists(profiles):
        with open(profiles, "w") as f:
            f.write(f"""{Path(base_dir).name}:
  target: dev
  outputs:
    dev:
      type: postgres
      host: localhost
      user: username
      password: password
      port: 5432
      dbname: database
      schema: public
      threads: 4
""")

    # -------------------------
    # .gitignore
    # -------------------------
    gitignore = os.path.join(base_dir, ".gitignore")
    if not os.path.exists(gitignore):
        with open(gitignore, "w") as f:
            f.write("""target/
logs/
dbt_packages/
__pycache__/
*.pyc
""")

    print(f"Created dbt project under: {base_dir}")

    for d in dirs:
        print(f"  [dir]  {d}")

    print(f"  [file] {dbt_project}")
    print(f"  [file] {packages}")
    print(f"  [file] {profiles}")
    print(f"  [file] {gitignore}")



def load_project_name():
    """Read project name from scripts/config/project_config.yml."""
    config_path = SCRIPTS_DIR / "config" / "project_config.yml"

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    return config["dbt"]["profile_name"]
project_name = load_project_name()

# Create project outside the scripts folder
project_dir = ROOT_DIR / project_name

print(f"Project name : {project_name}")
print(f"Project path : {project_dir}")

create_dbt_structure(project_dir)
