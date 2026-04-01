#!/usr/bin/env python3
"""CDK app entrypoint — multi-stage deployment.

Stage selection (default: dev):
    cdk deploy --all --context stage=dev
    cdk deploy --all --context stage=staging
    cdk deploy --all --context stage=production

Required context:
    stage         dev | staging | production  (default: dev)
    account       AWS account ID             (or set CDK_DEFAULT_ACCOUNT)
    region        AWS region                 (or set CDK_DEFAULT_REGION)

Optional context:
    github_repo   Full GitHub HTTPS URL — required for AmplifyStack.
                  e.g. https://github.com/your-org/OptionsLab

Full example:
    cdk deploy --all \\
        --context stage=production \\
        --context account=123456789012 \\
        --context region=us-east-1 \\
        --context github_repo=https://github.com/your-org/OptionsLab

Stack names:
    dev        TradingDataStack-dev   TradingApiStack-dev   TradingAmplifyStack-dev
    staging    TradingDataStack-staging  ...
    production TradingDataStack       TradingApiStack       TradingAmplifyStack
"""

import aws_cdk as cdk

from infrastructure.config import get_env_config
from infrastructure.stacks.amplify_stack import AmplifyStack
from infrastructure.stacks.api_stack import ApiStack
from infrastructure.stacks.data_stack import DataStack

app = cdk.App()

# ------------------------------------------------------------------ #
# Resolve stage and per-stage configuration
# ------------------------------------------------------------------ #
stage: str = app.node.try_get_context("stage") or "dev"
account: str | None = app.node.try_get_context("account") or None
region: str | None = app.node.try_get_context("region") or None

config = get_env_config(stage, account=account, region=region)

env = cdk.Environment(account=config.account, region=config.region)

# ------------------------------------------------------------------ #
# Stack 1 — VPC + RDS PostgreSQL
# ------------------------------------------------------------------ #
data_stack = DataStack(
    app,
    f"TradingDataStack{config.stack_suffix}",
    config=config,
    env=env,
)

# ------------------------------------------------------------------ #
# Stack 2 — Lambda + API Gateway
# ------------------------------------------------------------------ #
api_stack = ApiStack(
    app,
    f"TradingApiStack{config.stack_suffix}",
    config=config,
    data_stack=data_stack,
    env=env,
)
api_stack.add_dependency(data_stack)

# ------------------------------------------------------------------ #
# Stack 3 — Amplify Hosting  (only when github_repo is provided)
# ------------------------------------------------------------------ #
github_repo: str | None = app.node.try_get_context("github_repo")
if github_repo:
    amplify_stack = AmplifyStack(
        app,
        f"TradingAmplifyStack{config.stack_suffix}",
        config=config,
        api_url=api_stack.api_url,
        github_repo=github_repo,
        env=env,
    )
    amplify_stack.add_dependency(api_stack)

app.synth()
