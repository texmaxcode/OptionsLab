"""CDK stack: AWS Amplify Hosting for the Next.js frontend.

Prerequisites (one-time, manual):
  Store a GitHub personal access token in Secrets Manager:

    aws secretsmanager create-secret \\
        --name options-lab/github-token \\
        --secret-string '<YOUR_GITHUB_PAT>'

  The same token is shared across all stages; only one secret is needed.
"""

import aws_cdk as cdk
from aws_cdk import (
    CfnOutput,
    Stack,
    aws_amplify as amplify,
)
from constructs import Construct

from infrastructure.config import EnvironmentConfig

_GITHUB_TOKEN_SECRET = "options-lab/github-token"

# Inline build spec (repo-root amplify.yml takes precedence when present)
_BUILD_SPEC = """\
version: 1
applications:
  - appRoot: web
    frontend:
      phases:
        preBuild:
          commands:
            - npm ci
        build:
          commands:
            - npm run build
      artifacts:
        baseDirectory: .next
        files:
          - '**/*'
      cache:
        paths:
          - node_modules/**/*
          - .next/cache/**/*
      customHeaders:
        - pattern: '**/*'
          headers:
            - key: Strict-Transport-Security
              value: 'max-age=31536000; includeSubDomains'
            - key: X-Frame-Options
              value: SAMEORIGIN
            - key: X-Content-Type-Options
              value: nosniff
            - key: Referrer-Policy
              value: strict-origin-when-cross-origin
        - pattern: '_next/static/**/*'
          headers:
            - key: Cache-Control
              value: 'public, max-age=31536000, immutable'
"""

# Branch tracked per stage: dev → develop, staging → staging, prod → main
_BRANCH_MAP = {
    "dev": "develop",
    "staging": "staging",
    "production": "main",
}


class AmplifyStack(Stack):
    """AWS Amplify Hosting app for the Next.js dashboard.

    Each stage gets its own Amplify app and tracks a different git branch:
      dev        → 'develop' branch
      staging    → 'staging' branch
      production → 'main' branch

    NEXT_PUBLIC_API_URL is injected automatically from ApiStack's output.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: EnvironmentConfig,
        api_url: str,
        github_repo: str,
        branch: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        tracked_branch = branch or _BRANCH_MAP.get(config.stage, "main")

        # CloudFormation dynamic reference — resolved at deploy time,
        # never written in plaintext to the synthesised template.
        github_token = cdk.SecretValue.secrets_manager(_GITHUB_TOKEN_SECRET)

        app = amplify.CfnApp(
            self,
            "OptionsLabWebApp",
            name=f"options-lab{config.stack_suffix}",
            repository=github_repo,
            oauth_token=github_token.unsafe_unwrap(),
            build_spec=_BUILD_SPEC,
            platform="WEB_COMPUTE",   # SSR mode for Next.js App Router
            environment_variables=[
                amplify.CfnApp.EnvironmentVariableProperty(
                    name="NEXT_PUBLIC_API_URL",
                    value=api_url,
                ),
                amplify.CfnApp.EnvironmentVariableProperty(
                    name="NEXT_PUBLIC_APP_ENV",
                    value=config.stage,
                ),
            ],
            custom_rules=[
                # Fallback for client-side navigation (SPA catch-all)
                amplify.CfnApp.CustomRuleProperty(
                    source="/<*>",
                    target="/index.html",
                    status="404-200",
                ),
            ],
        )

        amplify.CfnBranch(
            self,
            "TrackedBranch",
            app_id=app.attr_app_id,
            branch_name=tracked_branch,
            enable_auto_build=True,
            description=f"{config.stage} branch",
        )

        app_url = f"https://{tracked_branch}.{app.attr_app_id}.amplifyapp.com"

        CfnOutput(self, "AmplifyAppId", value=app.attr_app_id)
        CfnOutput(self, "AmplifyUrl", value=app_url)
        CfnOutput(self, "AmplifyBranch", value=tracked_branch)
        CfnOutput(
            self,
            "ApiUrlInjected",
            value=api_url,
            description="API URL set as NEXT_PUBLIC_API_URL in this Amplify app",
        )
