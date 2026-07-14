import argparse
import os
import sys
import yaml
import requests
import getpass
import time
import github
from github import Github, GithubException
import snowflake.connector
import subprocess
import shutil
import tempfile

def compile_yaml_config_structure(inputs):
    """Transforms raw dictionary inputs into the structured branch layout matrix."""
    config = {
        "repo_name": inputs['repo_name'], 
        "owner": inputs['owner'],
        "project_name": inputs.get('project_name') or inputs.get('project_description', 'Universal Engine'), 
        "default_branch": inputs['branch_sequence'][0],
        "branches": {}
    }
    
    profiles = inputs.get('environment_profiles') or inputs.get('branch_data')
    if not profiles:
        print("❌ Configuration Error: Could not find an 'environment_profiles' or 'branch_data' block.")
        sys.exit(1)
        
    for idx, b in enumerate(inputs['branch_sequence']):
        b_inputs = profiles[b]
        is_last = (idx == len(inputs['branch_sequence']) - 1)
        b_cfg = {
            "protection": {
                "require_pr": b_inputs.get('require_pr', False), 
                "required_approvals": b_inputs.get('required_approvals', 0)
            },
            "approvers": {"groups": [], "individuals": b_inputs.get('approvers', [])},
            "environment": b,
            "environment_reviewers": {"groups": [], "individuals": b_inputs.get('approvers', [])}
        }
        if idx > 0: 
            b_cfg["source_branch"] = inputs['branch_sequence'][idx - 1]
        if is_last:
            config["final_branch"] = b
            b_cfg["locked"] = True
            b_cfg["protection"]["lock_branch"] = True
        config["branches"][b] = b_cfg
    return config

def set_github_env_variable(token, full_repo, env_name, var_name, var_value):
    """Securely uploads configuration values directly to the GitHub environment variable dashboard."""
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

def run_git_cmd(args, cwd=None, ignore_errors=False):
    """Helper engine to run native git commands silently via shell pipelines."""
    result = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0 and not ignore_errors:
        raise RuntimeError(f"Git execution error: {result.stderr.strip()}")
    return result.stdout

def generate_dcm_workflow(b_name, dcm_dir, central_repo, central_branch):
    return f"""name: "Snowflake DCM Infrastructure Pipeline - {b_name.upper()}"

on:
  pull_request:
    types: [opened, synchronize]
    branches:
      - {b_name}
    paths:
      - "{dcm_dir}/**"
  push:
    branches:
      - {b_name}
    paths:
      - "{dcm_dir}/**"

permissions:
  id-token: write
  contents: read

jobs:
  dcm-orchestration:
    if: (github.base_ref == '{b_name}' && github.event_name == 'pull_request') || (github.ref_name == '{b_name}' && github.event_name == 'push')
    uses: {central_repo}/.github/workflows/dcm-engine.yml@{central_branch}
    with:
      environment: {b_name}
"""

def generate_dbt_workflow(b_name, dbt_dir, central_repo, central_branch):
    return f"""name: "Snowflake dbt Transformation Pipeline - {b_name.upper()}"

on:
  pull_request:
    types: [opened, synchronize]
    branches:
      - {b_name}
    paths:
      - "{dbt_dir}/**"
  push:
    branches:
      - {b_name}
    paths:
      - "{dbt_dir}/**"

permissions:
  id-token: write
  contents: read

jobs:
  dbt-orchestration:
    if: (github.base_ref == '{b_name}' && github.event_name == 'pull_request') || (github.ref_name == '{b_name}' && github.event_name == 'push')
    uses: {central_repo}/.github/workflows/dbt-engine.yml@{central_branch}
    with:
      environment: {b_name}
"""

# ✅ SOLUTIONS FIX: Completely omits SNOWFLAKE_USER variable mapping to allow clean OIDC entry
def generate_snowflake_orchestration_workflow():
    return """name: "Snowflake Script Orchestration Matrix"
on:
  push:
    branches:
      - dev
      - qa
      - cicd
      - main
    paths:
      - "scripts/db_schema/**"
      - "scripts/config/**"
      - "scripts/dcm/**"
      - "scripts/**"
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
          python scripts/initialise_project.py --stop-on-error
"""

def main():
    parser = argparse.ArgumentParser(description="GitHub Safe Safe-Scaffold Engine")
    parser.add_argument("--input-file", required=True, help="Path to layout .yml file")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("❌ Error: GITHUB_TOKEN environment variable required.")
        sys.exit(1)

    with open(args.input_file, "r", encoding="utf-8") as f: 
        inputs = yaml.safe_load(f)
        
    compile_yaml_config_structure(inputs)
    g = Github(auth=github.Auth.Token(token))
    full_path = f"{inputs['owner']}/{inputs['repo_name']}"
    
    print("\nConnecting to GitHub...")
    try: 
        repo = g.get_repo(full_path)
        print(f"  [FOUND] Target repository '{full_path}' already exists. Transitioning to idempotent safe update mode.")
    except GithubException as e:
        if e.status == 404:
            print(f"  [MISSING] Target repository '{full_path}' missing. Provisioning fresh project...")
            try: 
                repo = g.get_user().create_repo(name=inputs['repo_name'], private=False)
            except GithubException:
                repo = g.get_organization(inputs['owner']).create_repo(name=inputs['repo_name'], private=False)
        else:
            sys.exit(1)

    profiles = inputs.get('environment_profiles') or inputs.get('branch_data')
    sf_global = inputs.get('snowflake_global') or {}

    # ==============================================================================
    # 🏗️ STEP 1: INITIALIZE ENVIRONMENT INJECTOR VARIABLE SECURE VAULTS
    # ==============================================================================
    print("\n[1/4] Synchronizing GitHub Backend Environments & Variable Vaults...")
    for b in inputs['branch_sequence']:
        env_profile = profiles[b]
        url = f"https://api.github.com/repos/{repo.full_name}/environments/{b}"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
        reviewers = [{"type": "User", "id": g.get_user(usr).id} for usr in env_profile.get('approvers', [])]
        payload = {"reviewers": reviewers, "deployment_branch_policy": {"protected_branches": False, "custom_branch_policies": True}} if reviewers else {}
        requests.put(url, headers=headers, json=payload)
        
        set_github_env_variable(token, full_path, b, "SNOWFLAKE_ACCOUNT", sf_global.get("account_identifier", ""))
        set_github_env_variable(token, full_path, b, "SNOWFLAKE_ROLE", sf_global.get("admin_role", ""))
        set_github_env_variable(token, full_path, b, "SNOWFLAKE_USER", env_profile.get("sf_user", ""))
        set_github_env_variable(token, full_path, b, "SNOWFLAKE_WAREHOUSE", sf_global.get("warehouse", ""))
        set_github_env_variable(token, full_path, b, "SNOWFLAKE_DATABASES", env_profile.get("sf_databases"))
        set_github_env_variable(token, full_path, b, "SNOWFLAKE_SCHEMAS", env_profile.get("sf_schemas"))
        set_github_env_variable(token, full_path, b, "DCM_TARGET", env_profile.get("dcm_target", ""))
        set_github_env_variable(token, full_path, b, "DCM_PROJECT_DIR", env_profile.get("dcm_dir", "dcm_automation"))
        set_github_env_variable(token, full_path, b, "DBT_PROJECT_DIR", env_profile.get("dbt_dir", "./dcm_dbt_cicd"))
        set_github_env_variable(token, full_path, b, "DBT_PROJECT_NAME_DEV", env_profile.get("dbt_project_dev", "dbt_project_dev"))
        set_github_env_variable(token, full_path, b, "DBT_PROJECT_NAME_PROD", env_profile.get("dbt_project_prod", "dbt_project_prod"))

    # ==============================================================================
    # ❄️ STEP 2: RESILIENT DATABASE OIDC USER REALIGNMENT
    # ==============================================================================
    sf_admin_user = os.environ.get("SNOWFLAKE_ADMIN_USER")
    sf_admin_password = os.environ.get("SNOWFLAKE_ADMIN_PASSWORD")
    if sf_global.get("account_identifier") and sf_admin_user and sf_admin_password:
        print("\n[2/4] Re-aligning Snowflake User OIDC Workload Identities dynamically...")
        try:
            ctx = snowflake.connector.connect(
                user=sf_admin_user, password=sf_admin_password,
                account=sf_global.get("account_identifier"),
                role=sf_global.get("admin_role"), warehouse=sf_global.get("warehouse")
            )
            cursor = ctx.cursor()
            for b in inputs['branch_sequence']:
                env_profile = profiles[b]
                target_user = env_profile.get("sf_user")
                if target_user:
                    dynamic_subject = f"repo:{inputs['owner']}/{inputs['repo_name']}:environment:{b}"
                    cursor.execute(f"ALTER USER {target_user} SET WORKLOAD_IDENTITY = (TYPE = OIDC, ISSUER = 'https://token.actions.githubusercontent.com', SUBJECT = '{dynamic_subject}');")
                    print(f"  ✔ Realigned: User '{target_user}' ➔ '{dynamic_subject}'")
            cursor.close()
            ctx.close()
        except Exception as sf_err:
            print(f"  ❌ Snowflake identity mapping alignment failed: {sf_err}")
    else:
        print("\n[2/4] ℹ️ Snowflake admin credentials omitted or skipped. Existing identity configurations preserved.")

    # ==============================================================================
    # 🚀 STEP 3: SAFE GIT SYNC ENGINE WITH TEMPORARY PROTECTION BYPASS
    # ==============================================================================
    # ==============================================================================
    # 🚀 CORRECTED STEP 3: HISTORY-ALIGNED GIT SYNC ENGINE
    # ==============================================================================
    source_repo_name = inputs.get('source_repository')
    source_branch_name = inputs.get('source_branch', 'main')
    
    if source_repo_name:
        print(f"\n[3/4] Initializing Safe Local Workspace Synchronization Engine...")
        with tempfile.TemporaryDirectory() as temp_dir:
            source_clone_dir = os.path.join(temp_dir, "source_template")
            auth_src_url = f"https://x-access-token:{token}@github.com/{source_repo_name}.git"
            run_git_cmd(["git", "clone", "--depth", "1", "--branch", source_branch_name, auth_src_url, source_clone_dir])
            
            folders_to_copy = inputs.get('folders_to_copy', [])
            files_to_copy = inputs.get('files_to_copy', [])
            target_push_url = f"https://x-access-token:{token}@github.com/{full_path}.git"
            
            # 🏁 CRITICAL CORRECTION: Establish ONE unified base directory for the entire repo lifecycle
            shared_repo_workspace = os.path.join(temp_dir, "unified_project_repo")
            default_b = inputs['branch_sequence'][0] # Usually 'dev'
            
            # Try to pull the baseline repo down if it exists, otherwise bootstrap a single root
            try:
                run_git_cmd(["git", "clone", target_push_url, shared_repo_workspace])
                print(f"    Target repository historical footprint found. Pulling unified graph...")
                repo_existed = True
            except Exception:
                os.makedirs(shared_repo_workspace, exist_ok=True)
                run_git_cmd(["git", "init"], cwd=shared_repo_workspace)
                run_git_cmd(["git", "remote", "add", "origin", target_push_url], cwd=shared_repo_workspace)
                
                # Write a single universal root commit to tie all future branches together forever
                with open(os.path.join(shared_repo_workspace, "README.md"), "w", encoding="utf-8") as rf:
                    rf.write(f"# {inputs['repo_name']}\nGitOps Unified Multi-Target Framework Core Hierarchy.")
                run_git_cmd(["git", "config", "user.name", "Automation Provisioner Service"], cwd=shared_repo_workspace)
                run_git_cmd(["git", "config", "user.email", "provisioner@internal.ops"], cwd=shared_repo_workspace)
                run_git_cmd(["git", "checkout", "-b", default_b], cwd=shared_repo_workspace)
                run_git_cmd(["git", "add", "README.md"], cwd=shared_repo_workspace)
                run_git_cmd(["git", "commit", "-m", "Initialize universal root commit ancestor"], cwd=shared_repo_workspace)
                run_git_cmd(["git", "push", "-u", "origin", default_b, "--force"], cwd=shared_repo_workspace)
                repo_existed = True

            # Process every branch out of the same synchronized commit graph layout
            for b in inputs['branch_sequence']:
                print(f"  ⚡ Synchronizing codebase states safely for branch: [{b.upper()}]")
                
                # Temporarily lower the gates for the incoming push packet
                headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
                prot_url = f"https://api.github.com/repos/{full_path}/branches/{b}/protection"
                requests.delete(prot_url, headers=headers)
                
                # Checkout or create the branch off the shared root history
                run_git_cmd(["git", "fetch", "origin"], cwd=shared_repo_workspace)
                try:
                    run_git_cmd(["git", "checkout", b], cwd=shared_repo_workspace)
                    run_git_cmd(["git", "pull", "origin", b], cwd=shared_repo_workspace)
                except Exception:
                    run_git_cmd(["git", "checkout", default_b], cwd=shared_repo_workspace)
                    run_git_cmd(["git", "checkout", "-b", b], cwd=shared_repo_workspace)

                # Clean the workspace paths before overlaying templates to prevent duplicate ghost files
                for f in files_to_copy:
                    p = os.path.join(shared_repo_workspace, f.strip())
                    if os.path.exists(p): os.remove(p)
                for folder in folders_to_copy:
                    d = os.path.join(shared_repo_workspace, folder.strip())
                    if os.path.exists(d) and folder.strip() != ".github": shutil.rmtree(d)

                # Overlay configuration assets
                for standalone_file in files_to_copy:
                    src_f = os.path.join(source_clone_dir, standalone_file.strip())
                    if os.path.exists(src_f):
                        shutil.copy2(src_f, os.path.join(shared_repo_workspace, standalone_file.strip()))
                        
                # Overlay directory infrastructure paths
                for folder_tree in folders_to_copy:
                    src_d = os.path.join(source_clone_dir, folder_tree.strip())
                    if os.path.exists(src_d) and folder_tree.strip() != ".github":
                        shutil.copytree(src_d, os.path.join(shared_repo_workspace, folder_tree.strip()))
                
                # Generate specific workflow structures inside the branch context
                wf_dir = os.path.join(shared_repo_workspace, ".github", "workflows")
                os.makedirs(wf_dir, exist_ok=True)
                
                env_profile = profiles[b]
                dcm_path = str(env_profile.get("dcm_dir", "dcm_automation")).lstrip("./")
                dbt_path = str(env_profile.get("dbt_dir", "dcm_dbt_cicd")).lstrip("./")
                
                with open(os.path.join(wf_dir, f"dcm-pipeline-{b}.yml"), "w", encoding="utf-8") as wf:
                    wf.write(generate_dcm_workflow(b, dcm_path, source_repo_name, source_branch_name))
                with open(os.path.join(wf_dir, f"dbt-pipeline-{b}.yml"), "w", encoding="utf-8") as wf:
                    wf.write(generate_dbt_workflow(b, dbt_path, source_repo_name, source_branch_name))
                with open(os.path.join(wf_dir, "snowflake-orchestration.yml"), "w", encoding="utf-8") as wf:
                    wf.write(generate_snowflake_orchestration_workflow())
                
                # Check status and perform incremental update push
                run_git_cmd(["git", "add", "."], cwd=shared_repo_workspace)
                status = run_git_cmd(["git", "status", "--porcelain"], cwd=shared_repo_workspace)
                
                if status.strip():
                    print(f"    Changes detected in infrastructure components. Pushing update packet...")
                    run_git_cmd(["git", "commit", "-m", "Idempotent refresh of GitOps platform workflows and assets"], cwd=shared_repo_workspace)
                    run_git_cmd(["git", "push", "origin", b], cwd=shared_repo_workspace)
                    print(f"    ✔ Branch updates successfully pushed.")
                else:
                    print(f"    No changes identified on branch tier [{b.upper()}]. Codebase is fully synchronized.")
    else:
        print("\n[3/4] Skipping code cloning stages (No source repository provided).")

    # ==============================================================================
    # 🔒 LOCKDOWN: BRANCH PROTECTION ENFORCEMENT LAST
    # ==============================================================================
    print("\n[4/4] Restoring branch protection laws and promotion gates...")
    for b in inputs['branch_sequence']:
        try:
            env_profile = profiles[b]
            if env_profile.get("require_pr"):
                url = f"https://api.github.com/repos/{full_path}/branches/{b}/protection"
                headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
                payload = {
                    "required_status_checks": None, "enforce_admins": True,
                    "required_pull_request_reviews": {"dismiss_stale_reviews": True, "required_approving_review_count": int(env_profile.get("required_approvals", 1))},
                    "restrictions": None
                }
                requests.put(url, headers=headers, json=payload)
                print(f"  ✔ Rules successfully activated on branch tier: [{b.upper()}]")
        except Exception as e: 
            print(f"  ⚠ Skipped branch protection rules on branch '{b}': {e}")
        time.sleep(0.1)
    print("\n🎉 Safe, idempotent platform matrix run successfully complete!")

if __name__ == "__main__": 
    main()
