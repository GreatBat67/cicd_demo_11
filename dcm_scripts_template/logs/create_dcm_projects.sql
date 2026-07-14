-- ====================================================
-- CREATE DCM PROJECTS
-- ====================================================

-- ----------------------------------------------------
-- Environment : DEV
-- ----------------------------------------------------
USE ROLE GITHUB_CICD_DEMO_ROLE;
USE DATABASE CICD_AUTOMATION_DEV;
USE SCHEMA CICD_AUTOMATION_DEV.UTILITIES;

CREATE DCM PROJECT IF NOT EXISTS CICD_AUTOMATION_DEV.UTILITIES.dcm_automation
COMMENT = 'DCM Project - DEV';

-- ----------------------------------------------------
-- Environment : QA
-- ----------------------------------------------------
USE ROLE GITHUB_CICD_DEMO_ROLE;
USE DATABASE CICD_AUTOMATION_QA;
USE SCHEMA CICD_AUTOMATION_QA.UTILITIES;

CREATE DCM PROJECT IF NOT EXISTS CICD_AUTOMATION_QA.UTILITIES.dcm_automation
COMMENT = 'DCM Project - QA';

-- ----------------------------------------------------
-- Environment : PROD
-- ----------------------------------------------------
USE ROLE GITHUB_CICD_DEMO_ROLE;
USE DATABASE CICD_AUTOMATION_PROD;
USE SCHEMA CICD_AUTOMATION_PROD.UTILITIES;

CREATE DCM PROJECT IF NOT EXISTS CICD_AUTOMATION_PROD.UTILITIES.dcm_automation
COMMENT = 'DCM Project - PROD';
