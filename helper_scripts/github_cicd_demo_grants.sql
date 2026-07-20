-- GitHub CI/CD demo: create service users with OIDC workload identity and grant roles
-- Co-authored with CoCo

-- Requires CREATE USER privilege; PSEUDO_SYSADMIN does not have it.
USE ROLE PSEUDO_ACCOUNTADMIN;

-- ==============================================================================
-- 1. DEVELOPMENT ENVIRONMENT GATE
-- ==============================================================================
CREATE OR REPLACE USER github_cicd_demo_dev_user
    TYPE = SERVICE
    WORKLOAD_IDENTITY = (
        TYPE = OIDC,
        ISSUER = 'https://token.actions.githubusercontent.com',
        SUBJECT = 'repo:GreatBat67/cicd_demo_11:environment:dev'
    );

GRANT ROLE github_cicd_demo_role TO USER github_cicd_demo_dev_user;

-- ==============================================================================
-- 2. QUALITY ASSURANCE ENVIRONMENT GATE
-- ==============================================================================
CREATE OR REPLACE USER github_cicd_demo_qa_user
    TYPE = SERVICE
    WORKLOAD_IDENTITY = (
        TYPE = OIDC,
        ISSUER = 'https://token.actions.githubusercontent.com',
        SUBJECT = 'repo:GreatBat67/cicd_demo_11:environment:qa'
    );

GRANT ROLE github_cicd_demo_role TO USER github_cicd_demo_qa_user;

-- ==============================================================================
-- 3. CONTINUOUS INTEGRATION / STAGING GATE
-- ==============================================================================
CREATE OR REPLACE USER github_cicd_demo_cicd_user
    TYPE = SERVICE
    WORKLOAD_IDENTITY = (
        TYPE = OIDC,
        ISSUER = 'https://token.actions.githubusercontent.com',
        SUBJECT = 'repo:GreatBat67/cicd_demo_11:environment:cicd'
    );

GRANT ROLE github_cicd_demo_role TO USER github_cicd_demo_cicd_user;

-- ==============================================================================
-- 4. PRODUCTION / MAIN ENVIRONMENT GATE
-- ==============================================================================
CREATE OR REPLACE USER github_cicd_demo_main_user
    TYPE = SERVICE
    WORKLOAD_IDENTITY = (
        TYPE = OIDC,
        ISSUER = 'https://token.actions.githubusercontent.com',
        SUBJECT = 'repo:GreatBat67/cicd_demo_11:environment:main'
    );

GRANT ROLE github_cicd_demo_role TO USER github_cicd_demo_main_user;

-- ==============================================================================
-- 5. SCHEMA PRIVILEGES FOR DBT PROJECT DEPLOYMENT
-- ==============================================================================

--run for different schema AVAILABLE or need to run 
GRANT CREATE DBT PROJECT ON SCHEMA CICD_DEMO_PROD.hospitals TO ROLE github_cicd_demo_role;
GRANT CREATE DBT PROJECT ON SCHEMA CICD_DEMO_PROD.UTILITIES TO ROLE github_cicd_demo_role;
GRANT CREATE DBT PROJECT ON SCHEMA CICD_DEMO_PROD.patients TO ROLE github_cicd_demo_role;

