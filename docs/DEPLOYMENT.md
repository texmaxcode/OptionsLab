# Deployment Guide

OptionsLab uses **AWS CDK (Python)** as the single source of truth for all cloud resources. The same stack code is deployed to three stages — `dev`, `staging`, and `production` — with different resource sizes and lifecycle policies.

---

## Architecture

```
GitHub repo
  │
  ├── push to any branch  ──▶  test.yml (pytest + lint + cdk synth)
  ├── push to main        ──▶  deploy-staging.yml  ──▶  staging AWS account
  └── push tag v*.*.*     ──▶  deploy-production.yml ──▶  prod AWS account
```

```
                         ┌──────────────────────────────────────────────┐
                         │  Browser                                     │
                         │    │                                         │
                         │    ▼                                         │
                         │  Amplify Hosting (WEB_COMPUTE / SSR)         │
                         │  https://<branch>.<app-id>.amplifyapp.com    │
                         │    │  NEXT_PUBLIC_API_URL                    │
                         │    ▼                                         │
                         │  API Gateway v2 (HTTP API)                   │
                         │    │                                         │
                         │    ▼                                         │
                         │  Lambda (Docker, Python 3.12, 512–1024 MB)   │
                         │  ├── JWT secret ──▶ Secrets Manager          │
                         │  └── DB secret  ──▶ Secrets Manager          │
                         │       │                                      │
                         │       ▼                                      │
                         │  RDS PostgreSQL 16 (private subnet)          │
                         └──────────────────────────────────────────────┘
```

---

## Stage comparison

| Setting | dev | staging | production |
|---|---|---|---|
| Stack name suffix | `-dev` | `-staging` | *(none)* |
| Git branch (Amplify) | `develop` | `staging` | `main` |
| RDS instance | t3.micro | t3.micro | t3.small |
| RDS Multi-AZ | No | No | Yes |
| RDS deletion protection | No | No | Yes |
| DB removal policy | DESTROY | SNAPSHOT | RETAIN |
| Lambda memory | 512 MB | 1024 MB | 1024 MB |
| Log retention | 7 days | 30 days | 90 days |
| API docs (`/docs`) | Enabled | Enabled | **Disabled** |
| JWT secret name | `options-lab/dev/jwt-secret` | `options-lab/staging/jwt-secret` | `options-lab/production/jwt-secret` |

All settings are in **`infrastructure/config.py`** and can be modified without touching stack code.

---

## Prerequisites

### Tools

| Tool | Version | Install |
|---|---|---|
| Python | ≥ 3.12 | system or pyenv |
| Node.js | ≥ 18 | [nodejs.org](https://nodejs.org) |
| AWS CLI v2 | latest | [Install guide](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) |
| AWS CDK CLI | ≥ 2.170 | `npm install -g aws-cdk` |
| Docker | Desktop / Engine | [docs.docker.com](https://docs.docker.com/get-docker/) |

> Docker must be **running** during `cdk deploy TradingApiStack*` — CDK builds the Lambda Docker image locally and pushes it to ECR.

### AWS setup

1. Create separate AWS accounts for staging and production (recommended) or use one account with separate stacks.
2. Configure AWS CLI profiles:

   ```bash
   aws configure --profile staging
   aws configure --profile production
   ```

3. Bootstrap CDK once per account/region:

   ```bash
   cdk bootstrap aws://<STAGING_ACCOUNT>/<REGION> --profile staging
   cdk bootstrap aws://<PROD_ACCOUNT>/<REGION> --profile production
   ```

---

## Manual deployment

### Install CDK dependencies

```bash
cd infrastructure
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Dev

```bash
# From the repo root:
npm run deploy:dev

# With explicit account/region:
cd infrastructure
cdk deploy --all \
    --context stage=dev \
    --context account=<ACCOUNT_ID> \
    --context region=us-east-1
```

### Staging

```bash
npm run deploy:staging

# Or manually:
cd infrastructure
cdk deploy --all \
    --context stage=staging \
    --context account=<STAGING_ACCOUNT_ID> \
    --context region=us-east-1 \
    --context github_repo=https://github.com/your-org/OptionsLab
```

### Production

```bash
npm run deploy:production

# Or manually:
cd infrastructure
cdk deploy --all \
    --context stage=production \
    --context account=<PROD_ACCOUNT_ID> \
    --context region=us-east-1 \
    --context github_repo=https://github.com/your-org/OptionsLab
```

### Review before deploying

```bash
# See what would change without deploying:
npm run diff:staging
npm run diff:production
```

---

## CI/CD (GitHub Actions)

Three workflows live in `.github/workflows/`:

| File | Trigger | What it does |
|---|---|---|
| `test.yml` | Every push / PR | pytest, frontend lint+build, CDK synth for all 3 stages |
| `deploy-staging.yml` | Push to `main` | Deploys all staging stacks, runs health-check smoke test |
| `deploy-production.yml` | Tag `v*.*.*` or manual dispatch | Deploys all production stacks with confirmation guard |

### GitHub setup

1. Create two GitHub Environments in your repo settings: **`staging`** and **`production`**.
2. Add required protection rules on `production` (e.g. required reviewer).
3. Add secrets and variables to each environment:

**Environment: `staging`**

| Type | Key | Value |
|---|---|---|
| Secret | `STAGING_AWS_ACCESS_KEY_ID` | IAM access key for staging account |
| Secret | `STAGING_AWS_SECRET_ACCESS_KEY` | IAM secret key for staging account |
| Variable | `AWS_ACCOUNT_ID` | Staging AWS account ID |
| Variable | `AWS_REGION` | e.g. `us-east-1` |
| Variable | `GITHUB_REPO_URL` | e.g. `https://github.com/org/OptionsLab` |

**Environment: `production`**

| Type | Key | Value |
|---|---|---|
| Secret | `PROD_AWS_ACCESS_KEY_ID` | IAM access key for production account |
| Secret | `PROD_AWS_SECRET_ACCESS_KEY` | IAM secret key for production account |
| Variable | `AWS_ACCOUNT_ID` | Production AWS account ID |
| Variable | `AWS_REGION` | e.g. `us-east-1` |
| Variable | `GITHUB_REPO_URL` | e.g. `https://github.com/org/OptionsLab` |

### Deploying a production release

```bash
git tag v1.2.3
git push origin v1.2.3
```

This triggers `deploy-production.yml`. The GitHub Environment protection rules run first (e.g. a required reviewer must approve).

---

## Environment variables reference

### Lambda (set automatically by CDK)

| Variable | Description |
|---|---|
| `APP_ENV` | `dev` / `staging` / `production` — controls CORS, docs visibility, logging |
| `TRADING_DATABASE_SECRET_ARN` | RDS Secrets Manager ARN (username + password) |
| `TRADING_DB_HOST` | RDS hostname |
| `TRADING_DB_PORT` | RDS port (5432) |
| `TRADING_DB_NAME` | Database name (`trading`) |
| `JWT_SECRET_KEY_ARN` | Secrets Manager ARN for the JWT signing key |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins (set from `config.allowed_origins`) |
| `MPLBACKEND` | `Agg` — headless matplotlib |

### Lambda (set manually after deploy)

Set these in the Lambda Console → Configuration → Environment variables, or via AWS CLI:

```bash
aws lambda update-function-configuration \
    --function-name options-lab-api-staging \
    --environment "Variables={MASSIVE_API_KEY=...,ETrade_SANDBOX=true}" \
    --region <REGION>
```

| Variable | Description |
|---|---|
| `MASSIVE_API_KEY` | Massive.com historical data API key |
| `ETrade_CONSUMER_KEY` / `ETrade_CONSUMER_SECRET` | E*TRADE app credentials |
| `ETrade_SANDBOX` | `true` (sandbox) / `false` (live) |
| `APCA_API_KEY_ID` / `APCA_API_SECRET_KEY` | Alpaca paper trading credentials |
| `FRED_API_KEY` / `BLS_API_KEY` / `BEA_API_KEY` | Economic data API keys |
| `OPENAI_API_KEY` | OpenAI for Research Assistant (optional) |
| `JWT_SECRET_KEY` | Overrides Secrets Manager — only for local/dev use |

### Next.js (Amplify — set by CDK)

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_API_URL` | API Gateway URL injected at build time |
| `NEXT_PUBLIC_APP_ENV` | `dev` / `staging` / `production` |

### Next.js (local development)

```bash
cp web/.env.local.example web/.env.local
# Edit NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Secrets Manager summary

| Secret name | Created by | Per stage? | Contents |
|---|---|---|---|
| `options-lab/<stage>/jwt-secret` | CDK `ApiStack` (auto) | Yes | 64-char JWT signing key |
| `<rds-auto-secret>` | CDK `DataStack` (auto) | Yes | JSON: username, password, host, port, dbname |
| `options-lab/github-token` | **You** (manual, once) | No (shared) | GitHub PAT for Amplify |

---

## Customising resource sizes

All tunable values are in `infrastructure/config.py`. Edit the `_dev()`, `_staging()`, or `_production()` factory functions:

```python
# infrastructure/config.py

def _production(account, region):
    return EnvironmentConfig(
        stage="production",
        db_instance_class="r7g.large",   # larger instance
        db_multi_az=True,
        lambda_memory_mb=2048,           # more Lambda memory
        log_retention_days=365,          # 1-year log retention
        allowed_origins=[               # restrict CORS
            "https://app.yourdomain.com",
        ],
        ...
    )
```

Then run `npm run diff:production` to preview the change before applying.

---

## Health check

Every deployed API exposes `GET /health`:

```bash
curl https://<api-url>/health
# 200 OK
{
  "status": "ok",
  "version": "v1.2.3",
  "environment": "production",
  "checks": { "database": "ok" }
}

# 503 Service Unavailable (DB unreachable)
{
  "status": "degraded",
  "checks": { "database": "error" }
}
```

---

## Costs (approximate, us-east-1)

| Service | dev | staging | production |
|---|---|---|---|
| RDS (t3.micro/small) | ~$15 | ~$15 | ~$30 |
| NAT Gateway | ~$32 | ~$32 | ~$32 |
| Lambda + ECR | ~$1 | ~$2 | ~$5 |
| API Gateway v2 | ~$0 | ~$1 | ~$1 |
| Amplify Hosting | ~$0 | ~$2 | ~$5 |
| Secrets Manager | ~$0.12 | ~$0.12 | ~$0.12 |
| **Total/month** | **~$48** | **~$52** | **~$73** |

> **Tip:** Delete the dev stack when not actively developing:
> `npm run destroy:dev`  (RDS removal policy is `DESTROY` for dev — no snapshot.)

---

## Teardown

```bash
# Dev (no final snapshot — fast)
npm run destroy:dev

# Staging (creates RDS snapshot before deletion)
npm run destroy:staging

# Production — RDS has RETAIN policy; instance is NOT deleted
# You must delete it manually from the RDS console after verifying the snapshot.
npm run destroy:production
```

Note: JWT secrets have `RemovalPolicy.RETAIN` on all stages. Delete manually if needed:

```bash
aws secretsmanager delete-secret \
    --secret-id options-lab/production/jwt-secret \
    --force-delete-without-recovery \
    --region <REGION>
```

---

## Troubleshooting

### `Error: ContextProvider...` during synth

CDK needs to resolve VPC/subnet info at synth time. Run `cdk synth` with real AWS credentials configured for the target account.

### Lambda 502 after deploy

Check CloudWatch Logs → `/aws/lambda/options-lab-api[-staging|-dev]`. Common causes:
- Missing Secrets Manager permissions
- RDS security group not allowing Lambda SG on port 5432
- Cold start timeout (increase `lambda_timeout_s` in `config.py`)

### `cdk synth` succeeds locally but fails in CI

Ensure the GitHub Actions environment has the correct AWS account ID and region variables. CDK bootstrap must have been run for the target account/region.

### Amplify build fails: `NEXT_PUBLIC_API_URL is undefined`

The variable is injected by the AmplifyStack. If you deployed Amplify manually (not via CDK), add it in the Amplify Console → App settings → Environment variables, then retrigger the build.
