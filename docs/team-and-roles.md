# Team and roles

Who Vizient needs to assemble to deploy, run and extend Vizient Contract Intelligence: what each person does, the access or
license they must hold, and when they are needed. It is written for whoever will staff the work. The procedures are in the
[deployment runbook](./deployment-runbook.md) and the [operations runbook](./operations-runbook.md); this document says who
does them.

> **Validation status.** Access requirements come from the templates, scripts and runbooks in this repository and, where
> cited, from Microsoft Learn. The deployment runbook has not been run from a clean start in a second tenant, so these are
> not proven minimums, and **no effort has been measured for any role**: do not size the team from this file. "Needs" is
> what the code or the platform requires. "Recommended" is advice. During the first development run, record each role's
> time and blockers, and correct this file.

## 1. The short version

| Group | Roles |
|---|---|
| Decide and approve | Business owner, Delivery lead, Security and compliance reviewer, Legal and privacy counsel, Licensing and cost owner |
| Provide access and platforms | Azure platform owner, Cloud governance administrator, Network engineer (private networking only), Microsoft Entra administrator, Power Platform administrator, SharePoint site owner |
| Build and change | Technical lead, Backend developer, Power Platform developer, Front-end developer, Release engineer, Evaluation lead |
| Run and use | Operations analyst, Checklist experts and reviewers |

- **Start with the people the developers depend on.** A development team cannot grant itself any of these: a
  subscription-level deployment with role assignments (Azure platform owner); an environment with code apps enabled, a
  permitted data policy and System Administrator (Power Platform administrator); licenses, groups and the account that owns
  the flows (Microsoft Entra administrator); the intake folder (SharePoint site owner); and a decision on real contracts
  (security and legal). Each depends on someone outside the development team, so ask for them first.
- **Four engineering skill areas are needed:** Python and Azure AI, Dataverse and Power Automate, React and TypeScript, and
  Azure infrastructure and release (section 5). One person can cover more than one; section 8 says which roles not to
  combine.
- **Business and legal people are part of the team.** A business owner owns the checklist, legal and security must decide
  before any real contract goes in, and contract staff review the findings and later help measure accuracy.
- **Most access roles have a short list of specific actions** (section 4). How much time each needs is not known yet.
- Section 9 lists what you do **not** need: an Entra app registration for the Function or the app, a data gateway, Copilot
  Studio skills, or a data scientist to train a model.

## 2. Who is needed when

**H** = hands-on, **A** = advises or approves, blank = not needed. The phases follow the runbooks:

- **Decide:** scope, real contracts, region, networking, who owns what (deployment runbook 2.4).
- **Prepare:** accounts, licenses, environment, intake folder, quota, policy (deployment runbook 2.1 to 2.3, 4.1 to 4.3, 5.1
  and 5.6).
- **Azure:** the Azure resources, the Function and the analyzer (deployment runbook 4.4 to 4.9).
- **Power Platform:** schema, connections, flows, the Code App, access (deployment runbook 5.2 to 5.9).
- **Verify:** the end-to-end checks with synthetic contracts (deployment runbook 6).
- **Pilot:** reviewers use it, and permissions are tested as a non-administrator (operations runbook 3.9 and 6).
- **Run:** operate and change it (operations runbook).

| Role | Decide | Prepare | Azure | Power Platform | Verify | Pilot | Run |
|---|---|---|---|---|---|---|---|
| Business owner | H | | | | A | H | A |
| Delivery lead | H | H | A | A | A | H | A |
| Security and compliance reviewer | A | A | | | A | A | A |
| Legal and privacy counsel | A | | | | | A | A |
| Licensing and cost owner | A | H | | | | | A |
| Azure platform owner | A | H | H | | A | | H |
| Cloud governance administrator | A | H | A | | | | A |
| Network engineer | A | H | A | | | | A |
| Microsoft Entra administrator | | H | | A | | H | H |
| Power Platform administrator | A | H | | H | A | H | H |
| SharePoint site owner | | H | | A | A | | A |
| Technical lead | H | A | H | H | H | H | H |
| Backend developer | | | H | | H | H | H |
| Power Platform developer | | | | H | H | H | H |
| Front-end developer | | | | H | H | H | H |
| Release engineer | | | A | A | | | H |
| Evaluation lead | | | | | A | H | H |
| Operations analyst | | | | | A | H | H |
| Checklist experts and reviewers | | | | | A | H | H |

## 3. The roles

### 3.1 Decide and approve

| Role | What they do for this project | Access or license they need |
|---|---|---|
| Business owner | Owns the outcome and the checklist: what the 20 extracted items mean and what a good result is. Decides whether real contracts are in scope and whether Q&A stays (it cannot be turned off today, deployment runbook 1). Accepts the pilot | Reviewer access, to see what reviewers see |
| Delivery lead | Raises the access requests, tracks approvals and the decisions in section 6, fills in the ownership table (operations runbook 1) before go-live, and makes sure the access roles are available for the first deployment | None |
| Security and compliance reviewer | Reviews what is stored where (the PDF, page text and extraction result in Dataverse, page chunks in Azure AI Search, action data in flow run history), how the Function key is held, where models may process prompts (`GlobalStandard` may process in any Azure region), whether to use private networking, and whether the review step meets Vizient's policy on AI use. Signs off before any real contract is processed | Read-only: Reader on the resource group and a read role in the Dataverse environment. No change rights |
| Legal and privacy counsel | Decides whether Vizient policy and the contracts' own confidentiality terms allow processing signed contracts with these services. Sets retention and deletion for Dataverse and Search content (none exists yet), with the records manager, and decides how AI results and reviewer decisions are kept as records | None |
| Licensing and cost owner | Confirms licenses: for the Code App, Power Apps Premium, pay-as-you-go, an App Pass or auto-claim; for the flows, whether the flow owner's license covers the HTTP action (deployment runbook 2.2). Decides the budget and watches the spend. Azure AI Search is about USD 74 a month at list price while it exists, even idle (a dated estimate, deployment runbook Appendix D) | Cost Management Reader on the subscription. Creating a budget takes Cost Management Contributor or Contributor at that scope, so the Azure platform owner creates it |

### 3.2 Provide access and platforms

| Role | What they do for this project | Access or license they need |
|---|---|---|
| Azure platform owner | Chooses the region, confirms model quota, registers resource providers, runs `azd provision` and `azd deploy`, reads the preview before every provision, creates the budget and cost alert, and assigns data-plane roles to other developers (section 4.1) | **Owner** on the target subscription, or Contributor plus User Access Administrator (Role Based Access Control Administrator also covers the role-assignment part). The template deploys at subscription scope and writes role assignments (deployment runbook 2.1) |
| Cloud governance administrator | Says in advance which Azure Policy and tagging rules apply (public network access on storage accounts, required tags, allowed regions, private endpoints), approves any exception through Vizient's process, and re-checks after policy changes | Read access to policy assignments and compliance, and a role that can create exemptions (for example Resource Policy Contributor) if one is granted |
| Network engineer (private networking only) | Allocates the VNet address space, fits the private DNS zone into Vizient's DNS design, and owns the network security groups and any route table on the Function subnet (section 4.5) | Reader on the resource group; Network Contributor to change the network after deployment |
| Microsoft Entra administrator | Creates the security groups (reviewers, maintainers). Assigns licenses, which a Power Platform administrator cannot. Creates the dedicated account that owns the flow connections. Assigns the Power Platform administrator role to a person. Advises when Conditional Access blocks a script's sign-in. Optionally creates a service principal for automation (section 4.3) | A role that can create users, manage groups and assign licenses (User Administrator covers all three), and Privileged Role Administrator to assign admin roles |
| Power Platform administrator | Creates the Dataverse-enabled environment, turns on **Enable code apps**, checks the data policy, gives the builders System Administrator, checks Dataverse capacity, assigns reviewer security roles and shares the app, and controls who can read environment variable values and flow run history (section 4.2) | The **Power Platform administrator** role, assigned directly to the person and not through a group. It does not carry System Administrator inside an environment (section 4.2) |
| SharePoint site owner | Creates the intake site, library and folder, gives the flow connection's account edit rights, and decides who can add files. That is one of three controls on what the pipeline processes (section 4.4) | Site owner of the intake site. A SharePoint administrator creates the site if self-service site creation is off |

### 3.3 Build and change

| Role | What they do for this project | Access or license they need |
|---|---|---|
| Technical lead | Owns the architecture and the repository, runs the first development deployment with the Azure platform owner and records where the runbooks differ from reality, and keeps changes inside the project's rules: everything in the solution, AI results immutable, a verbatim clause and page for every Found result, and one checklist file as the source of truth | Contributor on the development resource group once it exists (the Azure platform owner runs the subscription-scope provision), System Administrator in the development environment, and admin on the repository |
| Backend developer (Python, Azure AI) | The Function, the checklist and analyzer, model swaps, the Q&A agent and Search index, and the Python tests (section 5) | Contributor on the development resource group (`azd deploy` publishes with the deployer's Entra token) and the data-plane roles in deployment runbook Appendix B. The template assigns those to one user only (section 4.1) |
| Power Platform developer | The Dataverse schema, the four flows (`scripts/flowlib.py`, never the designer), connection references and environment variables, solution export, and the least-privilege security roles the solution does not define yet | System Administrator in the development environment (what the provisioning scripts need, deployment runbook 2.1) and a license that gives access to Dataverse data. Also Azure access to list the Function's host keys (for example Contributor on the Function app): `provision-flow.py` reads the key through Azure, even for `--status`. Otherwise the Azure platform owner runs that script |
| Front-end developer | The Code App: screens, filters, the PDF evidence viewer, the generated Dataverse services, and `pa app push`. Screen work can start against mock data (`npm run dev:mock`) | At least the Environment Maker role in the development environment (**Recommended**). It gives no access to Dataverse data, so also a role on the `vz_` tables to test with data (for example the reviewer role once it exists), code apps enabled, and a license that can run code apps. What a non-administrator maker needs, including to add the app to the solution, is **Unverified**: the demonstration pushed as an administrator |
| Release engineer | Hosts the repository and adds the CI that does not exist yet (tests, leak scan, Bicep build, solution verification, a what-if), non-interactive deployment, promotion between environments (none today) and secret handling for the Function key | Admin on the repository, and a deployment identity created with the Microsoft Entra administrator and approved by the Azure platform owner (section 4.3). The template assigns the deployer's Azure roles with principal type `User`, so a service principal or workload identity cannot be the deployer without a template change |
| Evaluation lead | Owns accuracy. Builds gold labels for real contracts with the checklist experts, scores them with `eval/score.py`, agrees the confidence threshold (`HIGH_CONF`) with the business owner, and re-scores after any model, checklist or prompt change. Real-contract accuracy has not been measured: the repository has gold labels for three synthetic contracts only. Gold labels quote the contract verbatim, so keep real-contract labels and saved results outside the repository, in a location the security reviewer approves (pass the folder to `eval/score.py --gold`). As a backstop, `.gitignore` ignores every file in `eval/gold` except the three synthetic sets, and all of `samples/`, and the synthetic-contract test fails if `eval/gold` holds any other set; neither protects any other location. `scripts/run-local.py` only checks for a "SYNTHETIC SAMPLE" marker, and `CONTRACT_DATA_MODE=real` turns that check off, so send real contracts only with the security reviewer's approval | Read access to findings and reviewer decisions in Dataverse, and Cognitive Services Content Understanding Reader on the extraction Foundry account to run `run-local.py` directly (the Function itself runs with that role). Running it with `--via function` needs the Function key instead |

### 3.4 Run and use

| Role | What they do for this project | Access or license they need |
|---|---|---|
| Operations analyst | Works the routine checks (operations runbook 2): contracts stuck in Extracting or Failed, indexing failures, failed flow runs, Function errors, throttling and cost. Retries contracts by setting a status (operations runbook 3.1 and 3.2) and escalates to the technical lead. Re-extraction (3.3) runs a script that deletes findings, including reviewer decisions, so keep it with a maintainer | A license that gives access to Dataverse data and write access to `vz_contract` (a retry sets Status or `vz_indexstatus`). Azure read access to Application Insights, Log Analytics and Foundry metrics (for example Reader and Log Analytics Reader), and Cost Management Reader if they check cost. Flow run history can show document content, so grant it deliberately (operations runbook 6) |
| Checklist experts and reviewers | Reviewers confirm, correct or reject each finding in the Code App. Experts own the wording of the 20 checklist items, judge the first results and write the answers used to measure accuracy | A license that can run code apps, a Dataverse security role (access to `vz_contract`, `vz_finding` and `vz_checklistitem`, own-row access to `vz_contractquestion`) and the app shared with them (operations runbook 3.9). The solution defines no such role yet |

## 4. What the access roles have to do

These roles gate everything else. The actions are in the order the runbooks need them.

### 4.1 Azure platform owner

1. Pick the region and confirm that Content Understanding, Flex Consumption and all five model deployments exist there, with
   quota (deployment runbook 2.2 and 4.3). Quota was the largest schedule risk identified when the demonstration was planned.
2. Register the resource providers (deployment runbook 4.2), including `Microsoft.Network` and `Microsoft.App` if you use
   private networking.
3. Agree the networking mode with the governance administrator and the network engineer (deployment runbook 2.4 and
   Appendix E).
4. Run `azd provision --preview --no-prompt`, read it, then `azd provision --no-prompt` and `azd deploy` (deployment runbook
   4.4 to 4.7).
5. Run the policy check in deployment runbook 4.6, and repeat it after any governance change. In the demonstration a policy
   changed the storage account about two weeks after deployment.
6. Create a budget and a cost alert on the resource group, for the amount the licensing and cost owner decides.
7. Give other developers the data-plane roles for the steps they run (deployment runbook, Appendix B): Content Understanding
   Contributor for `deploy_analyzer.py`, the Search and Foundry roles for `provision-qa.py`, and Content Understanding
   Reader for `run-local.py` run directly. The template assigns these roles to one user, the account that ran
   `azd provision`, so every other developer needs them assigned. The repository has no script for this, and assigning them
   to a group is **Unverified**.

Watch for: when azd reuses the Azure CLI sign-in, as the runbook sets it up, it follows the CLI's active subscription, not
`AZURE_ACCOUNT`, so check the account and subscription each tool will use before you provision (deployment runbook 4.1).
New Search capacity can be unavailable in the chosen region; set `AZURE_SEARCH_LOCATION` (deployment runbook 2.4).

### 4.2 Power Platform administrator

1. Create a Dataverse-enabled development environment, then the production one. If an environment has a security group, the
   builders and the reviewers must be in it.
2. Turn on **Enable code apps** for each environment (deployment runbook 5.1). Power Platform administrators and environment
   administrators can set it ([Microsoft Learn](https://learn.microsoft.com/power-apps/developer/code-apps/overview)).
3. Check the tenant and environment data policies. The flows use the SharePoint, Microsoft Dataverse and HTTP connectors, and
   the app uses Dataverse. A policy that blocks one of them, or splits them across groups, stops the flows from running.
4. Give the people who run the provisioning scripts the **System Administrator** role in the environment (deployment runbook
   2.1). The Power Platform administrator role does not do this by itself: Microsoft no longer assigns System Administrator
   automatically to the admin roles, and an admin must add themselves (the environment's **Membership** page) before they can
   change roles or install apps. The elevation is logged, and the person needs a license that gives access to Dataverse data
   ([Microsoft Learn](https://learn.microsoft.com/power-platform/admin/manage-high-privileged-admin-roles)).
5. Confirm Dataverse storage: each contract's PDF, its page text and a reduced extraction result are stored there
   (operations runbook 6).
6. Approve the connection owner and the connections (deployment runbook 5.5). Then restrict who can read environment variable
   values (the Function key is a text variable, deployment runbook 5.7) and who can open flow run history (operations
   runbook 6).
7. When the Power Platform developer has designed the reviewer role, give it to the reviewers and share the app (deployment
   runbook 5.9). To use the reviewers' Entra group, create a Dataverse group team for it in each environment and assign the
   role to the team. The app creates user-owned question rows, so the role needs member's privilege inheritance, or each
   reviewer needs the role directly. If the environment has a security group, the group team's Entra group must be a member
   of it ([Microsoft Learn](https://learn.microsoft.com/power-platform/admin/manage-group-teams)). None of this has been
   tested here (**Unverified**).

Watch for: this repository's solution snapshot leaves the Code App package out (it is git-ignored), so importing the
snapshot does not deploy the app; `pa app push` does (deployment runbook 5.8). Microsoft Learn says a code app that is in a
solution moves with an exported and imported solution
([Microsoft Learn](https://learn.microsoft.com/power-apps/developer/code-apps/how-to/alm)); that route was not tested here
(**Unverified**). There is no automated promotion between environments (operations runbook 3.10): repeat the steps in each
one.

### 4.3 Microsoft Entra administrator

1. Create two security groups: reviewers (to share the app and, through a Dataverse group team, to carry the Dataverse role)
   and maintainers (to carry the developer access in sections 4.1 and 4.2 above). **Recommended.**
2. Assign licenses to the reviewers and to the flow owner. A Power Platform administrator cannot
   ([Microsoft Learn](https://learn.microsoft.com/power-platform/admin/use-service-admin-role-manage-tenant)).
3. Create the dedicated account that owns the SharePoint and Dataverse connections. **Recommended**, and **Unverified**.
   Flows run as the connection owner: if that person's sign-in, license or consent changes, the flows that use the
   connection fail. All four use the Dataverse connection, and only the Intake flow uses SharePoint (operations runbook
   4.1). Agree how Conditional Access and multifactor authentication apply to the account.
4. Assign the Power Platform administrator role directly to the person (this takes the Privileged Role Administrator role).
   Role assignment through groups is not supported for it. If Vizient uses Privileged Identity Management, expect
   time-limited activation: Microsoft removes a self-elevated System Administrator role when the activation expires.
5. Be the contact when a script's sign-in is blocked by Conditional Access or consent. The Dataverse scripts accept a service
   principal or a certificate (`CLIENT_ID` with `CLIENT_SECRET` or `CLIENT_CERTIFICATE_PATH` in `.env`), and
   `pa app push --non-interactive` can run as a service principal, which needs access to the environment and edit access to
   the app, shared with it once by a maker
   ([Microsoft Learn](https://learn.microsoft.com/power-apps/developer/code-apps/how-to/use-service-principal)). The Azure
   side differs: the template assigns the deployer's roles with principal type `User`, so a service principal cannot run
   `azd provision` without a template change. The repository has no pipeline, and none of this has been tested here.

### 4.4 SharePoint site owner

1. Create the site, the library and an intake folder, and note the library's GUID (deployment runbook 5.6).
2. Give the connection owner edit rights. The Intake flow reads the folder through that connection (deployment runbook
   2.1).
3. Decide who may add files. The pipeline processes any PDF that reaches the folder, and the real-contracts setting only
   looks for a text marker and does not gate extraction (deployment runbook 2.4). Three groups of people control what
   enters: those who can add files to the folder, those who can write `vz_contract` rows in Dataverse (setting Status to
   Extracting queues an analysis), and anyone holding the Function key, who can submit a PDF to the Function directly.
4. Tell users that PDFs over 4 MB fail: it is a Dataverse connector limit (deployment runbook 5.7).
5. Apply sensitivity labels and retention to the library. Nothing in this project deletes the original PDFs (operations
   runbook 6).

### 4.5 Governance and network

Cloud governance administrator: list the policies that will apply before the first deployment, and re-check after every
governance change (deployment runbook 4.6). The durable fix for a policy that disables public network access on storage is
private networking, not an exemption tag (deployment runbook 2.4).

Network engineer, when `ENABLE_PRIVATE_NETWORKING` is true (deployment runbook, Appendix E):

- Choose ranges that do not overlap Vizient's. The defaults are `10.20.0.0/24` with `10.20.0.0/27` for the Function subnet
  and `10.20.0.32/28` for the private endpoint subnet, and all three are Bicep parameters (deployment runbook 3.2).
- The template creates its own `privatelink.blob.core.windows.net` zone and links it to the new VNet. If Vizient manages
  private DNS centrally, or a policy creates DNS zone groups on private endpoints, expect to adapt `infra/app/network.bicep`.
  That case was not designed or tested.
- Flex Consumption sends all of the Function's outbound traffic through its subnet, so Vizient's network security group and
  route table rules on that subnet apply to its calls to Foundry and Search.
- It isolates the Function's storage only. The Function keeps a public inbound endpoint, which the flows call with a
  function key. A private inbound endpoint is not part of this design.
- If Defender for Storage malware scanning is on, check that its rule is still in the storage firewall after each provision.

## 5. Engineering skills

| Area | Where | Skills | Typical changes |
|---|---|---|---|
| Function and AI | [function/](../function/), [checklist/](../checklist/), [analyzer/](../analyzer/), [eval/](../eval/), [provision-qa.py](../scripts/provision-qa.py) | Python 3.12, Azure Functions, managed identity and Entra tokens, Azure Content Understanding, Foundry prompt agents and model deployments, Azure AI Search | Change an extraction rule, add a checklist item, swap a model, republish the Q&A agent (operations runbook 3.6, 3.7 and 3.10) |
| Dataverse and flows | [dataverse/](../dataverse/), [flowlib.py](../scripts/flowlib.py), [provision-dataverse.py](../scripts/provision-dataverse.py), [provision-flow.py](../scripts/provision-flow.py) | Dataverse tables, choices, relationships and Web API; solutions, publishers, connection references and environment variables; cloud flow definitions (JSON) | Add a column, change a flow, design security roles |
| Code App | [contract-review/](../contract-review/) | React 19, strict TypeScript, Fluent UI v9, pdf.js, Vite, Vitest, ESLint; the Power Apps CLI (`pa`) and SDK | Change screens, regenerate the data services after a schema change, `pa app push` (deployment runbook 5.8) |
| Infrastructure and release | [infra/](../infra/), [azure.yaml](../azure.yaml) | Bicep, Azure Developer CLI, Azure RBAC and policy, PowerShell, networking if private, a CI system | Change capacity (operations runbook 3.8), enable private networking (deployment runbook, Appendix E), add CI (not covered by the runbooks) |

Operations runbook 3.10 maps each kind of change to what to edit and which checks follow. The tools to install are in
deployment runbook 2.3.

Developers who change Azure, the schema or the flows need a development resource group and a development Dataverse
environment, not the ones reviewers use; screen work can start against mock data (`npm run dev:mock`). Each developer keeps
their own git-ignored `.env`. Most scripts check the signed-in account against `AZURE_ACCOUNT` and three do not (deployment
runbook 2.1), so confirm which identity each tool will use.

## 6. Owners and decision makers

The operations runbook (section 1) has an ownership table to fill in before go-live. Suggested owners:

| Responsibility | Suggested owner |
|---|---|
| Azure subscription, budget and cost alerts | The licensing and cost owner decides the amount and watches the spend; the Azure platform owner creates the budget and the alerts |
| Azure resources and model quota | Azure platform owner |
| Function key rotation (operations runbook 3.5) | Azure platform owner and Power Platform developer, together: the steps run back to back, and between them every flow call fails with 401 |
| Dataverse environment and the solution | Power Platform administrator for the environment; Power Platform developer for the solution |
| Owner of the flow connections | A dedicated account created by the Microsoft Entra administrator, with a named custodian and a backup. **Recommended**, **Unverified** |
| Reviewer access and licenses | Microsoft Entra administrator for licenses and groups; Power Platform administrator for the security role and the app share |
| Code App releases | Front-end developer, approved by the technical lead |
| Incident triage | Operations analyst first, then the technical lead |
| Contract data retention and deletion | Legal and privacy counsel decide. The Power Platform administrator (Dataverse), the SharePoint site owner (the originals) and the backend developer (Search) carry it out. Only `purge-contract-index.py` exists, and it removes Search chunks only; the other deletions are manual and have no procedure yet (operations runbook 6) |

Decisions that only these people can make:

| Decision | Who decides | Where it is described |
|---|---|---|
| Keep Q&A (it cannot be switched off today) | Business owner and technical lead | Deployment runbook 1 |
| Whether real contracts are allowed, and on what conditions | Business owner, with security and legal | Deployment runbook 2.4 |
| Where models may process prompts (`GlobalStandard` or a data zone) | Security and legal; the Azure platform owner implements | Deployment runbook 2.4 |
| Private networking or an approved exception | Cloud governance administrator, network engineer and Azure platform owner | Deployment runbook 2.4, Appendix E |
| Who owns the flow connections | Microsoft Entra administrator and Power Platform administrator | Operations runbook 4.1 |
| Retention and deletion | Legal and privacy counsel | Operations runbook 6 |
| How the Function key is stored | Security reviewer and release engineer | Operations runbook 6 |
| The reviewer security role (least privilege) | Power Platform developer and security reviewer | Operations runbook 6 |
| Who can open flow run history | Power Platform administrator and security reviewer | Operations runbook 6 |
| Alerts and monitoring | Operations analyst and Azure platform owner | Operations runbook 5 |
| Promotion between environments | Release engineer and Power Platform administrator | Operations runbook 3.10 |
| What accuracy is good enough | Business owner and evaluation lead | Operations runbook 6 |

## 7. Before the first deployment: what to ask each role for

**Azure platform owner**

- [ ] A development subscription, and **Owner** (or Contributor plus User Access Administrator) for the deployer.
- [ ] The region confirmed, and quota for the five model deployments confirmed or requested (deployment runbook 2.2).
- [ ] Resource providers registered (deployment runbook 4.2).
- [ ] A budget and a cost alert, and a named backup.

**Cloud governance administrator and network engineer**

- [ ] The policies that will apply, and the decision between private networking and an approved exception (deployment
  runbook 2.4).
- [ ] With private networking: address ranges that do not overlap Vizient's, and the DNS approach.

**Microsoft Entra administrator**

- [ ] Security groups for reviewers and maintainers.
- [ ] Licenses for the reviewers and for the flow owner.
- [ ] The dedicated connection-owner account, with its Conditional Access treatment agreed.
- [ ] The Power Platform administrator role assigned to a named person.

**Power Platform administrator**

- [ ] A Dataverse-enabled development environment, with the builders in its security group if it has one.
- [ ] **Enable code apps** turned on.
- [ ] A data policy that allows SharePoint, Microsoft Dataverse and HTTP together.
- [ ] System Administrator for the people who run the provisioning scripts.
- [ ] Dataverse storage capacity confirmed.

**SharePoint site owner**

- [ ] The intake site, library and folder, and the library's GUID.
- [ ] Edit rights for the connection owner, and an agreed list of who can add files.

**Security reviewer and legal counsel**

- [ ] A written position on real contracts and on where models may process prompts.
- [ ] A named reviewer for the design before the first deployment.

**Business owner**

- [ ] Whether Q&A stays in scope.
- [ ] The checklist owner, the pilot reviewers and the pilot's acceptance criteria.

## 8. Staffing a small team

One person can hold several roles. These combinations are **Recommended**, not required by the code:

| Combination | Verdict | Why |
|---|---|---|
| Azure platform owner and cloud governance administrator | Works | The same subscription and policy knowledge |
| Technical lead, backend developer and release engineer | Works for a pilot | Keep a second person able to deploy |
| Power Platform administrator and Power Platform developer | Works in development; separate them in production | The administrator should approve the data policy and security roles that the developer designs |
| Business owner and checklist expert | Works | The person who defines the wording judges the results |
| Security reviewer and the person who deploys | Avoid | The reviewer should not approve their own deployment |
| A developer's personal account as the connection owner | Avoid | The flows that use its connections fail when that person's sign-in, license or consent changes (operations runbook 4.1) |
| One person holding the Azure, Power Platform or connection-owner role with no backup | Avoid | Each controls something nobody else can grant |

Team size and time commitments are to be set after the first development run (the acceptance test for the runbooks), which
is the place to measure what each role needs. The roles in section 1 are the list to staff against, not a headcount, and the
build team has to cover the four skill areas in section 5.

The access roles should be available, even only on call, whenever someone deploys or changes the system. Without them a
developer stalls at the sign-in check (deployment runbook 4.1), at turning on code apps (deployment runbook 5.1) and at
creating the connections (deployment runbook 5.5).

## 9. What you do not need

- **An Entra app registration for the Function or the Code App.** The Function runs as a managed identity and the flows call
  it with a function key; users reach the app through the Power Apps host (operations runbook 6). A service principal is
  optional, for automation (section 4.3).
- **An on-premises data gateway.** SharePoint, Dataverse and the call to the Function are all cloud services. The Function
  keeps a public inbound endpoint (deployment runbook, Appendix E); a private inbound endpoint is not part of this design and
  was not tested.
- **Copilot Studio skills.** The Q&A agent is a Foundry prompt agent that `scripts/provision-qa.py` publishes, and the
  reviewer screen is a Power Apps Code App.
- **A data scientist to train a model.** Extraction uses Azure Content Understanding with an analyzer generated from the
  checklist and a hosted model. Nobody at Vizient trains a model; the evaluation lead measures one.
