import os
import yaml
import sys
from pathlib import Path
sys.dont_write_bytecode = True

# scripts directory
SCRIPTS_DIR = Path.cwd().parent

# project root (parent of scripts)
ROOT_DIR = SCRIPTS_DIR.parent


def load_project_name():
    """Read project name from scripts/config/project_config.yml."""
    config_path = SCRIPTS_DIR / "config" / "project_config.yml"

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    return config["project"]["name"]

def create_dcm_structure(base_dir):
    """Creates the DCM project folder structure under base_dir."""
    dirs = [
        base_dir,
        os.path.join(base_dir, "sources"),
        os.path.join(base_dir, "sources", "definitions"),
        os.path.join(base_dir, "sources", "macros"),
        os.path.join(base_dir, "out"),
        os.path.join(base_dir, "out", "analyze"),
        os.path.join(base_dir, "out", "analyze", "analyze_dependencies_output"),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)

    # Create placeholder manifest.yml at root
    manifest_root = os.path.join(base_dir, "manifest.yml")
    if not os.path.exists(manifest_root):
        open(manifest_root, "w").close()

    # Create analyze_dependencies.json
    deps_json = os.path.join(base_dir, "out", "analyze", "analyze_dependencies.json")
    if not os.path.exists(deps_json):
        open(deps_json, "w").close()

    # Create manifest.yml inside analyze_dependencies_output
    manifest_output = os.path.join(base_dir, "out", "analyze", "analyze_dependencies_output", "manifest.yml")
    if not os.path.exists(manifest_output):
        open(manifest_output, "w").close()

    print(f"Created DCM folder structure under: {base_dir}")
    for d in dirs:
        print(f"  [dir]  {d}")
    print(f"  [file] {manifest_root}")
    print(f"  [file] {deps_json}")
    print(f"  [file] {manifest_output}")


project_name = load_project_name()

# Create project outside the scripts folder
project_dir = ROOT_DIR / project_name

print(f"Project name : {project_name}")
print(f"Project path : {project_dir}")

create_dcm_structure(project_dir)
