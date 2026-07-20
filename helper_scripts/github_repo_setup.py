# Setup generalized, variable-tier infrastructure and separate workflow files dynamically with governance gates
"""
Usage (Automated Template Generation):
    python all_combined_14_7.py --input-file .\github_infra_config_v3.yaml

Requirements:
    pip install PyGithub PyYAML requests pynacl
"""

import argparse
import os
import sys
import yaml
import requests
import subprocess
import shutil
import tempfile
import time
import github
from github import Github, GithubException


def compile_yaml_config_structure(inputs):
    """Assembles an adaptive dictionary layout matching the user's custom branch list with robust key fallbacks[cite: 6, 8]."""
    config = {
        "repo_name": inputs['repo_name'],
        "owner": inputs['owner'],
        "project_name": inputs.get('project_name') or inputs.get('project_description', 'Snowflake Gated GitOps Core Offering'),
        "default_branch": inputs['branch_sequence'][0],
        "branches": {}
    }
    
    for idx, b in enumerate(inputs['branch_sequence']):
        b_inputs = inputs['branch_data'][b]
        is_last = (idx == len(inputs['branch_sequence']) - 1)
        
        b_cfg = {
            "protection": {
                "require_pr": b_inputs.get('require_pr', False),
                "required_approvals": b_inputs.get('required_approvals', 0)
            },
            "approvers": {"groups": [], "individuals": b_inputs.get('approvers', [])},
            "environment": b if b_inputs.get('has_snowflake', True) else None,
            "environment_reviewers": {"groups": [], "individuals": b_inputs.get('approvers', []) if b_inputs.get('has_snowflake', True) else []}
        }
        
        if idx > 0:
            b_cfg["source_branch"] = inputs['branch_sequence'][idx - 1]
            
        if is_last:
            config["final_branch"] = b
            b_cfg["locked"] = True
            b_cfg["protection"]["lock_branch"] = True
            b_cfg["protection"]["restrict_pushes"] = True
            
        config["branches"][b] = b_cfg
        
    return config


def execute_shell_cmd(args, cwd=None, ignore_errors=False):
    """Executes local Git shell routines with high performance[cite: 1, 6]."""
    result = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0 and not ignore_errors:
        raise RuntimeError(f"Shell execution failure: {result.stderr.strip()}")
    return result.stdout


def set_github_env_variable(token, full_repo, env_name, var_name, var_value):
    """Securely uploads configuration values directly to the GitHub environment variable dashboard panel[cite: 1, 6]."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    if isinstance(var_value, list):
        var_value = ",".join([str(v).strip() for v in var_value])
    elif var_value is None:
        var_value = ""
    check_url = f"https://api.github.com/repos/{full_repo}/environments/{env_name}/variables/{var_name}"
    resp = requests.get(check_url, headers=headers)
    payload = {"name": var_name, "value": str(var_value)}
    if resp.status_code == 200:
        requests.patch(check_url, headers=headers, json={"value": str(var_value)})
    else:
        create_url = f"https://api.github.com/repos/{full_repo}/environments/{env_name}/variables"
        requests.post(create_url, headers=headers, json=payload)


# ==========================================================
# 📋 DECOUPLED PIPELINE WORKFLOW BLUEPRINT GENERATORS
# ==========================================================

def generate_dcm_action_yml():
    """Generates the reusable composite module for Snowflake DCM tasks ensuring native OIDC context usage[cite: 1, 8]."""
    return """name: 'Snowflake DCM Execution Module'
description: 'Modular core engine managing Snowflake database infrastructure changes via DCM'
inputs:
  dcm_dir:
    description: 'Path directory holding dcm configurations'
    required: true
  dcm_target:
    description: 'Target profile environment label'
    required: true
  action_type:
    description: 'Execution context mode (plan or deploy)'
    required: true
runs:
  using: "composite"
  steps:
    - name: Setup Snowflake CLI (OIDC)
      uses: snowflakedb/snowflake-cli-action@v2.0
      with:
        use-oidc: true
    - name: Execute Targeted DCM Operations
      shell: bash
      run: |
        cd ${{ inputs.dcm_dir }}
        if [ "${{ inputs.action_type }}" = "plan" ]; then
          echo "Processing structural change mappings execution dry-run..."
          snow dcm plan --target ${{ inputs.dcm_target }} -x
        else
          echo "LIVE: Pushing structural modifications directly into active database target..."
          snow dcm deploy --target ${{ inputs.dcm_target }} -x
        fi
"""


def generate_dbt_action_yml():
    """Generates the reusable composite module for Snowflake dbt transformations ensuring native OIDC context usage[cite: 1, 8]."""
    return """name: 'Snowflake dbt Transformation Module'
description: 'Modular core engine scheduling and compiling dbt project model targets'
inputs:
  dbt_dir:
    description: 'Path directory holding dbt models data'
    required: true
  dbt_project:
    description: 'Target dbt project profile context label'
    required: true
  dcm_target:
    description: 'Target operational database destination map'
    required: true
  action_type:
    description: 'Execution context mode (plan or deploy)'
    required: true
runs:
  using: "composite"
  steps:
    - name: Setup Snowflake CLI (OIDC)
      uses: snowflakedb/snowflake-cli-action@v2.0
      with:
        use-oidc: true
    - name: Execute Targeted dbt Transformations
      shell: bash
      run: |
        if [ "${{ inputs.action_type }}" = "plan" ]; then
          echo "Compiling structural transform configurations against virtual target..."
          snow dbt deploy ${{ inputs.dbt_project }} --source ${{ inputs.dbt_dir }} --force -x
        else
          echo "LIVE: Synchronizing and deploying live production dbt model transforms..."
          snow dbt deploy ${{ inputs.dbt_project }} --source ${{ inputs.dbt_dir }} --force -x
          snow dbt execute -x ${{ inputs.dbt_project }} run --target ${{ inputs.dcm_target }}
        fi
"""


def generate_manual_init_yml():
    """Generates the bootstrap initializer runner matching Snowflake Script Orchestration Matrix parameters exactly."""
    return """name: "Snowflake Script Orchestration Matrix"
on:
  push:
    branches:
      - dev
      - qa
      - cicd
      - main
    paths:
      - "dcm_scripts_template/db_schema/**"
      - "dcm_scripts_template/config/**"
      - "dcm_scripts_template/dcm/**"
      - "dcm_scripts_template/projects/**"
      - "dcm_scripts_template/dbt/**"
      - "dcm_scripts_template/logs/**"
  workflow_dispatch:
permissions:
  id-token: write
  contents: read
jobs:
  execute-orchestrator:
    runs-on: ubuntu-latest
    environment: ${{ github.ref_name == 'main' && 'main' || github.ref_name }}
    steps:
      - name: "Checkout Repository Codebase"
        uses: actions/checkout@v4
      - name: "Set up Enterprise Python Environment"
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"
          cache-dependency-path: "./requirements.txt"
      - name: "Install Core Python Dependencies"
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - name: "Initialize Snowflake CLI Context Interface"
        uses: snowflakedb/snowflake-cli-action@v2.0
        with:
          use-oidc: true
      - name: "Generate OIDC Token with Correct Snowflake Audience"
        uses: actions/github-script@v7
        with:
          script: |
            const token = await core.getIDToken('snowflakecomputing.com')
            core.exportVariable('SNOWFLAKE_TOKEN', token)
      - name: "Execute Custom Python Automation Orchestrator Pipeline"
        env:
          SNOWFLAKE_ACCOUNT: "${{ vars.SNOWFLAKE_ACCOUNT }}"
          SNOWFLAKE_ROLE: "${{ vars.SNOWFLAKE_ROLE }}"
          SNOWFLAKE_WAREHOUSE: "${{ vars.SNOWFLAKE_WAREHOUSE }}"
          SNOWFLAKE_DATABASE: "${{ vars.SNOWFLAKE_DATABASES }}"
          SNOWFLAKE_SCHEMA: "${{ vars.SNOWFLAKE_SCHEMAS }}"
        run: |
          echo "🚀 Initializing Orchestrator Pipeline Run for Tier: [${{ github.ref_name }}]"
          
          # 🏁 FIX: Dynamically discovers the orchestrator script path to avoid naming errors completely
          SCRIPT_PATH=$(find . -name "initialise_project.py" | head -n 1)
          
          if [ -z "$SCRIPT_PATH" ]; then
            echo "❌ Fatal Error: Could not locate initialise_project.py in the workspace tree."
            exit 1
          fi
          
          echo "🎯 Executing resolved script path location: $SCRIPT_PATH"
          python "$SCRIPT_PATH" --stop-on-error
"""


def generate_dynamic_pr_gate_yml(inputs):
    """Generates a sequential transition checker tailored to the custom branch sequence[cite: 8]."""
    workflow = """# Adaptive One-way PR gate enforcement workflow
name: Enforce One-Way PR Gate
on:
  pull_request:
    types: [opened, reopened, synchronize, edited]
    branches:"""
    
    for b in inputs['branch_sequence'][1:]:
        workflow += f"\n      - {b}"
        
    workflow += """

jobs:
  gate-check:
    runs-on: ubuntu-latest
    steps:"""
    
    for idx in range(1, len(inputs['branch_sequence'])):
        target = inputs['branch_sequence'][idx]
        source = inputs['branch_sequence'][idx - 1]
        
        workflow += f"""
      - name: Enforce {source} -> {target} gate
        if: github.event.pull_request.base.ref == '{target}' && github.event.pull_request.head.ref != '{source}'
        run: |
          echo "::error::PR routing violation. Merges into target branch '{target}' must originate from source branch '{source}'."
          exit 1"""
          
    workflow += """
      - name: Gate passed
        run: echo "Branch pipeline trajectory validated successfully."
"""
    return workflow


def generate_dynamic_master_delivery_yml(inputs):
    """Builds a centralized entry router linking custom branches directly to their dedicated layout files[cite: 8]."""
    monitored_paths = inputs.get('paths') or inputs.get('folders_to_copy', [])
    paths_str = "\n".join([f"      - '{p}/**'" if not p.endswith('/**') else f"      - '{p}'" for p in monitored_paths])
    branches_str = "\n".join([f"      - {b}" for b in inputs['branch_sequence'][1:]])
    
    template = """name: "Standard Tier: Automated Snowflake Delivery - Master"
on:
  workflow_dispatch:
  pull_request:
    types: [opened, synchronize]
    branches:
<BRANCHES_STR>
    paths:
<PATHS_STR>
  push:
    branches:
<BRANCHES_STR>
    paths:
<PATHS_STR>

permissions:
  id-token: write 
  contents: read

jobs:"""

    workflow = template.replace("<BRANCHES_STR>", branches_str).replace("<PATHS_STR>", paths_str)

    for b in inputs['branch_sequence']:
        b_inputs = inputs['branch_data'][b]
        if not b_inputs.get('has_snowflake', True):
            continue
            
        condition_str = f"(github.base_ref == '{b}' && github.event_name == 'pull_request') || (github.ref_name == '{b}' && github.event_name == 'push')"
            
        workflow += f"""
  {b}-environment-pipeline:
    if: {condition_str}
    uses: ./.github/workflows/snowflake-pipeline-{b}.yml
    secrets: inherit
"""
    return workflow


def generate_dynamic_branch_pipeline_yml(b_name, b_inputs, inputs):
    """Creates a standalone workflow leveraging the modular composite architecture actions[cite: 1, 8]."""
    sf_global = inputs.get('snowflake_global', {})
    sf_account = sf_global.get('account_identifier') or inputs.get('sf_account', '')
    sf_role = sf_global.get('admin_role') or inputs.get('sf_role', '')
    sf_warehouse = sf_global.get('warehouse') or inputs.get('sf_warehouse', '')

    sf_db = b_inputs.get('sf_databases', [''])[0] if isinstance(b_inputs.get('sf_databases'), list) else b_inputs.get('sf_db', '')
    sf_schema = b_inputs.get('sf_schemas', [''])[0] if isinstance(b_inputs.get('sf_schemas'), list) else b_inputs.get('sf_schema', '')

    template = """name: "Snowflake Component: Progression Target - <B_NAME>"
on:
  workflow_call:

env:
  SNOWFLAKE_ACCOUNT: "<SF_ACCOUNT>"
  SNOWFLAKE_ROLE: "<SF_ROLE>"
  SNOWFLAKE_WAREHOUSE: "<SF_WAREHOUSE>"
  SNOWFLAKE_CLI_FEATURES_ENABLE_SNOWFLAKE_PROJECTS: "true"
  SNOWFLAKE_DATABASE: "<SF_DB>"
  SNOWFLAKE_SCHEMA: "<SF_SCHEMA>"

jobs:
  <B_NAME>-environment-plan:
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    environment: <B_NAME> 
    steps:
      - uses: actions/checkout@v4
      
      - name: Run Modular Infrastructure Verification (DCM Plan)
        uses: ./.github/workflows/modules/action-dcm-engine
        with:
          dcm_dir: "<DCM_PROJECT_DIR>"
          dcm_target: "<DCM_TARGET>"
          action_type: "plan"
          
      - name: Run Modular Data Transformation Verification (dbt Plan)
        uses: ./.github/workflows/modules/action-dbt-engine
        with:
          dbt_dir: "<DBT_SOURCE_DIR>"
          dbt_project: "<DBT_PROJECT_DEV>"
          dcm_target: "<DCM_TARGET>"
          action_type: "plan"

  <B_NAME>-environment-deploy:
    if: github.event_name == 'push'
    runs-on: ubuntu-latest
    environment: <B_NAME> 
    steps:
      - uses: actions/checkout@v4
      
      - name: Live Deploy to Database Target (DCM Deploy)
        uses: ./.github/workflows/modules/action-dcm-engine
        with:
          dcm_dir: "<DCM_PROJECT_DIR>"
          dcm_target: "<DCM_TARGET>"
          action_type: "deploy"
          
      - name: Live Database Content Transformations (dbt Deploy)
        uses: ./.github/workflows/modules/action-dbt-engine
        with:
          dbt_dir: "<DBT_SOURCE_DIR>"
          dbt_project: "<DBT_PROJECT_PROD>"
          dcm_target: "<DCM_TARGET>"
          action_type: "deploy"
"""
    return (template
            .replace("<B_NAME>", b_name)
            .replace("<SF_ACCOUNT>", sf_account)
            .replace("<SF_ROLE>", sf_role)
            .replace("<SF_WAREHOUSE>", sf_warehouse)
            .replace("<SF_DB>", sf_db)
            .replace("<SF_SCHEMA>", sf_schema)
            .replace("<DCM_TARGET>", b_inputs.get('dcm_target', ''))
            .replace("<DCM_PROJECT_DIR>", b_inputs.get('dcm_dir') or inputs.get('dcm_project_dir', 'dcm_automation'))
            .replace("<DBT_SOURCE_DIR>", b_inputs.get('dbt_dir') or inputs.get('dbt_source_dir', './dcm_dbt_cicd'))
            .replace("<DBT_PROJECT_DEV>", b_inputs.get('dbt_project_dev', 'dbt_project_dev'))
            .replace("<DBT_PROJECT_PROD>", b_inputs.get('dbt_project_prod', 'dbt_project_prod')))


def main():
    parser = argparse.ArgumentParser(description="Autonomous Pipeline Execution Template Engine")
    parser.add_argument("--input-file", help="Path to pre-built YAML configuration input parameter file")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")

    if not token or token.strip() == "":
        print("CRITICAL EXCEPTION: Token variable is completely empty inside the execution script.")
        sys.exit(1)

    target_file = args.input_file if args.input_file else "pipeline_inputs_v2.yaml"
    
    if not os.path.exists(target_file):
        print(f"Error: Specified template matrix configuration path '{target_file}' does not exist.")
        sys.exit(1)
        
    print(f"Parsing configuration from: '{target_file}'...")
    with open(target_file, "r") as f:
        inputs = yaml.safe_load(f)
        
    inputs['default_branch'] = inputs['branch_sequence'][0]
    derived_yaml_config = compile_yaml_config_structure(inputs)
    
    auth = github.Auth.Token(token)
    g = Github(auth=auth)
    full_repo_path = f"{inputs['owner']}/{inputs['repo_name']}"
    
    try:
        repo = g.get_repo(full_repo_path)
        print(f"Target repository '{full_repo_path}' verified.")
    except GithubException as e:
        if e.status == 404:
            print(f"Target repository missing. Provisioning fresh project structure...")
            project_desc = inputs.get('project_description') or inputs.get('project_name', '')
            try:
                repo = g.get_user().create_repo(name=inputs['repo_name'], private=False, description=project_desc)
            except GithubException:
                repo = g.get_organization(inputs['owner']).create_repo(name=inputs['repo_name'], private=False, description=project_desc)
        else:
            sys.exit(1)

    # ==============================================================================
    # 🔐 STEP 1: PROVISION ENVIRONMENT DEPLOYMENT GATES & VARIABLE VAULTS
    # ==============================================================================
    print("\n[1/3] Synchronizing GitHub Backend Environments & Variable Vaults...")
    sf_global = inputs.get('snowflake_global', {})
    for b_name in inputs['branch_sequence']:
        b_inputs = inputs['branch_data'][b_name]
        
        # Configure target environment and reviews via HTTP API panel[cite: 1]
        url = f"https://api.github.com/repos/{repo.full_name}/environments/{b_name}"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
        reviewers = [{"type": "User", "id": g.get_user(usr).id} for usr in b_inputs.get('approvers', [])]
        payload = {"reviewers": reviewers, "deployment_branch_policy": {"protected_branches": False, "custom_branch_policies": True}} if reviewers else {}
        requests.put(url, headers=headers, json=payload)
        
        if b_inputs.get('has_snowflake', True):
            set_github_env_variable(token, full_repo_path, b_name, "SNOWFLAKE_ACCOUNT", sf_global.get("account_identifier", ""))
            set_github_env_variable(token, full_repo_path, b_name, "SNOWFLAKE_ROLE", sf_global.get("admin_role", ""))
            set_github_env_variable(token, full_repo_path, b_name, "SNOWFLAKE_USER", b_inputs.get("sf_user", ""))
            set_github_env_variable(token, full_repo_path, b_name, "SNOWFLAKE_WAREHOUSE", sf_global.get("warehouse", ""))
            set_github_env_variable(token, full_repo_path, b_name, "SNOWFLAKE_DATABASES", b_inputs.get("sf_databases", []))
            set_github_env_variable(token, full_repo_path, b_name, "SNOWFLAKE_SCHEMAS", b_inputs.get("sf_schemas", []))

    # ==============================================================================
    # 🚀 STEP 2: HIGH-PERFORMANCE LOCAL GIT SUBPROCESS ENGINE (BULK COPY & SYNC)
    # ==============================================================================
    print("\n[2/3] Executing High-Performance Local Workspace Synchronization...")
    src_url = inputs.get('source_repository', '')
    source_branch = inputs.get('source_branch', 'main')
    files_to_copy = inputs.get('files_to_copy', [])
    folders_to_copy = inputs.get('folders_to_copy', [])
    
    with tempfile.TemporaryDirectory() as temp_dir:
        source_clone_dir = os.path.join(temp_dir, "source_template")
        target_clone_dir = os.path.join(temp_dir, "target_workspace")
        
        # Clone base template repository footprints[cite: 1]
        if src_url:
            print("  ➔ Cloning baseline source template metadata paths...")
            auth_src_url = src_url.replace("https://github.com/", f"https://x-access-token:{token}@github.com/")
            execute_shell_cmd(["git", "clone", "--depth", "1", "--branch", source_branch, auth_src_url, source_clone_dir])

        # Setup local working mirror context linked directly to the target remote target[cite: 1]
        auth_target_url = f"https://x-access-token:{token}@github.com/{full_repo_path}.git"
        try:
            execute_shell_cmd(["git", "clone", auth_target_url, target_clone_dir])
            print("  ➔ Target remote architecture ancestral footprint resolved.")
        except Exception:
            os.makedirs(target_clone_dir, exist_ok=True)
            execute_shell_cmd(["git", "init"], cwd=target_clone_dir)
            execute_shell_cmd(["git", "remote", "add", "origin", auth_target_url], cwd=target_clone_dir)
            
            with open(os.path.join(target_clone_dir, "README.md"), "w", encoding="utf-8") as rf:
                rf.write(f"# {inputs['repo_name']}\nGitOps Enterprise Multi-Target Deployment Framework Hierarchy.")
            execute_shell_cmd(["git", "config", "user.name", "Automation Scaffolder Module"], cwd=target_clone_dir)
            execute_shell_cmd(["git", "config", "user.email", "automation@internal.ops"], cwd=target_clone_dir)
            execute_shell_cmd(["git", "checkout", "-b", inputs['branch_sequence'][0]], cwd=target_clone_dir)
            execute_shell_cmd(["git", "add", "README.md"], cwd=target_clone_dir)
            execute_shell_cmd(["git", "commit", "-m", "Initialize universal root tracking history context"], cwd=target_clone_dir)
            execute_shell_cmd(["git", "push", "-u", "origin", inputs['branch_sequence'][0], "--force"], cwd=target_clone_dir)

        # Loop branches and perform fast bulk additions inside the local disk cache directory
        for idx, b_name in enumerate(inputs['branch_sequence']):
            print(f"  ⚡ Fast-injecting dynamic delivery contexts into branch: [{b_name.upper()}]")
            
            # Temporarily clear rules out on GitHub layer to block server branch push conflicts[cite: 1]
            requests.delete(f"https://api.github.com/repos/{full_repo_path}/branches/{b_name}/protection", headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"})
            
            execute_shell_cmd(["git", "fetch", "origin"], cwd=target_clone_dir)
            try:
                execute_shell_cmd(["git", "checkout", b_name], cwd=target_clone_dir)
                execute_shell_cmd(["git", "pull", "origin", b_name], cwd=target_clone_dir)
            except Exception:
                if idx > 0:
                    try: execute_shell_cmd(["git", "checkout", inputs['branch_sequence'][idx - 1]], cwd=target_clone_dir)
                    except Exception: pass
                execute_shell_cmd(["git", "checkout", "-b", b_name], cwd=target_clone_dir)

            # Purge obsolete configurations instantly using bulk local operations[cite: 1]
            for target_file in files_to_copy:
                p = os.path.join(target_clone_dir, target_file.strip())
                if os.path.exists(p): os.remove(p)
            for target_folder in folders_to_copy:
                d = os.path.join(target_clone_dir, target_folder.strip())
                if os.path.exists(d) and target_folder.strip() != ".github": shutil.rmtree(d, ignore_errors=True)

            # Bulk mirror files directly from cached disk path[cite: 1]
            if src_url:
                for target_file in files_to_copy:
                    src_f = os.path.join(source_clone_dir, target_file.strip())
                    if os.path.exists(src_f): shutil.copy2(src_f, os.path.join(target_clone_dir, target_file.strip()))
                for target_folder in folders_to_copy:
                    src_d = os.path.join(source_clone_dir, target_folder.strip())
                    if os.path.exists(src_d) and target_folder.strip() != ".github":
                        shutil.copytree(src_d, os.path.join(target_clone_dir, target_folder.strip()))

            # Format and inject nested workflow directory configurations on disk[cite: 1]
            wf_dir = os.path.join(target_clone_dir, ".github", "workflows")
            mod_dcm_dir = os.path.join(wf_dir, "modules", "action-dcm-engine")
            mod_dbt_dir = os.path.join(wf_dir, "modules", "action-dbt-engine")
            os.makedirs(mod_dcm_dir, exist_ok=True)
            os.makedirs(mod_dbt_dir, exist_ok=True)

            with open(os.path.join(target_clone_dir, "github_gates_config.yaml"), "w", encoding="utf-8") as out:
                yaml.dump(derived_yaml_config, out, default_flow_style=False, sort_keys=False)
            with open(os.path.join(mod_dcm_dir, "action.yml"), "w", encoding="utf-8") as out: out.write(generate_dcm_action_yml())
            with open(os.path.join(mod_dbt_dir, "action.yml"), "w", encoding="utf-8") as out: out.write(generate_dbt_action_yml())
            with open(os.path.join(wf_dir, "pr-gate.yml"), "w", encoding="utf-8") as out: out.write(generate_dynamic_pr_gate_yml(inputs))
            with open(os.path.join(wf_dir, "snowflake-delivery-master.yml"), "w", encoding="utf-8") as out: out.write(generate_dynamic_master_delivery_yml(inputs))

            b_inputs = inputs['branch_data'][b_name]
            if b_inputs.get('has_snowflake', True):
                with open(os.path.join(wf_dir, f"snowflake-pipeline-{b_name}.yml"), "w", encoding="utf-8") as out:
                    out.write(generate_dynamic_branch_pipeline_yml(b_name, b_inputs, inputs))

            # 🏁 STAGE A PUSH: Push template assets and baseline pipelines first to avoid premature orchestration triggers[cite: 1]
            execute_shell_cmd(["git", "add", "."], cwd=target_clone_dir)
            status = execute_shell_cmd(["git", "status", "--porcelain"], cwd=target_clone_dir)
            if status.strip():
                execute_shell_cmd(["git", "commit", "-m", "Idempotent structural refresh of GitOps code template matrix modules"], cwd=target_clone_dir)
                execute_shell_cmd(["git", "push", "origin", b_name, "--force"], cwd=target_clone_dir)
                print("    ✔ Baseline assets and tracking pipelines pushed successfully.")

            # 🏁 STAGE B PUSH (LAST STEP): Inject the orchestration matrix workflow silently[cite: 1]
            orchestration_workflow_path = os.path.join(wf_dir, "snowflake-orchestration.yml")
            with open(orchestration_workflow_path, "w", encoding="utf-8") as out: 
                out.write(generate_manual_init_yml())

            execute_shell_cmd(["git", "add", orchestration_workflow_path], cwd=target_clone_dir)
            status_orch = execute_shell_cmd(["git", "status", "--porcelain"], cwd=target_clone_dir)
            if status_orch.strip():
                execute_shell_cmd(["git", "commit", "-m", "Deploy orchestration matrix master workflow as final step"], cwd=target_clone_dir)
                execute_shell_cmd(["git", "push", "origin", b_name], cwd=target_clone_dir)
                print("    ✔ Orchestration master workflow successfully deployed silently at last step.")
            else:
                print("    ℹ Orchestration master workflow is fully synchronized.")

    # ==============================================================================
    # 🔒 STEP 3: RESTORE SECURE GOVERNANCE RULESETS & CLAMP TRUNK LOCKS
    # ==============================================================================
    print("\n[3/3] Restoring branch protection rulesets and promotion gates...")
    for b_name in inputs['branch_sequence']:
        try:
            b_cfg = derived_yaml_config["branches"][b_name]
            protection = b_cfg.get("protection", {})
            is_locked = b_cfg.get("locked", False)
            branch_obj = repo.get_branch(b_name)
            
            if protection.get("require_pr", False) or is_locked:
                branch_obj.edit_protection(
                    enforce_admins=protection.get("enforce_admins", True),
                    dismiss_stale_reviews=protection.get("dismiss_stale_reviews", True),
                    require_code_owner_reviews=protection.get("require_code_owner_reviews", False),
                    required_approving_review_count=protection.get("required_approvals", 1)
                )
                if is_locked:
                    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
                    requests.put(f"https://api.github.com/repos/{full_repo_path}/branches/{b_name}/protection", headers=headers, json={
                        "required_status_checks": None, "enforce_admins": True,
                        "required_pull_request_reviews": {"required_approving_review_count": 1, "dismiss_stale_reviews": True},
                        "restrictions": None, "lock_branch": True
                    })
                print(f"  ✔ Policy rules successfully bound to branch tier reference: [{b_name.upper()}]")
        except Exception as e:
            print(f"  ⚠️ Skip protection logic assignment for [{b_name.upper()}]: {e}")
        time.sleep(0.1)

    print(f"\n{'='*80}\n 🎉 SUCCESS: Unified Modular GitOps Scaffolder Successfully Synchronized!\n{'='*80}\n")


if __name__ == "__main__":
    main()
