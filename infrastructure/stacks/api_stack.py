"""CDK stack: Lambda (Docker image) + HTTP API Gateway v2 for the trading API."""

from pathlib import Path

import aws_cdk as cdk  # noqa: F401
from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_apigatewayv2 as apigwv2,
    aws_apigatewayv2_integrations as integrations,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_secretsmanager as sm,
)
from constructs import Construct

from infrastructure.config import EnvironmentConfig
from infrastructure.stacks.data_stack import DataStack

_REPO_ROOT = str(Path(__file__).parents[2])

# Map common day counts to CloudWatch RetentionDays enum values.
_LOG_RETENTION_MAP: dict[int, logs.RetentionDays] = {
    1: logs.RetentionDays.ONE_DAY,
    3: logs.RetentionDays.THREE_DAYS,
    5: logs.RetentionDays.FIVE_DAYS,
    7: logs.RetentionDays.ONE_WEEK,
    14: logs.RetentionDays.TWO_WEEKS,
    30: logs.RetentionDays.ONE_MONTH,
    60: logs.RetentionDays.TWO_MONTHS,
    90: logs.RetentionDays.THREE_MONTHS,
    180: logs.RetentionDays.SIX_MONTHS,
    365: logs.RetentionDays.ONE_YEAR,
    731: logs.RetentionDays.TWO_YEARS,
    1827: logs.RetentionDays.FIVE_YEARS,
    3653: logs.RetentionDays.TEN_YEARS,
}


def _log_retention(days: int) -> logs.RetentionDays:
    return _LOG_RETENTION_MAP.get(days, logs.RetentionDays.TWO_WEEKS)


class ApiStack(Stack):
    """Docker-image Lambda + HTTP API Gateway v2.

    All sizing and lifecycle settings come from EnvironmentConfig so the same
    stack code produces different resources for dev / staging / production.

    Secrets created per stage (never shared across stages):
      options-lab/<stage>/jwt-secret   — JWT signing key (auto-generated)
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: EnvironmentConfig,
        data_stack: DataStack,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ------------------------------------------------------------------ #
        # JWT signing secret (auto-generated, per-stage)
        # ------------------------------------------------------------------ #
        jwt_secret = sm.Secret(
            self,
            "JwtSecret",
            secret_name=f"{config.secret_prefix}/jwt-secret",
            description=f"JWT signing key for OptionsLab ({config.stage})",
            generate_secret_string=sm.SecretStringGenerator(
                exclude_punctuation=True,
                password_length=64,
            ),
            # RETAIN so sessions survive a stack destroy/redeploy.
            removal_policy=RemovalPolicy.RETAIN,
        )

        # ------------------------------------------------------------------ #
        # Network: import Lambda SG created by DataStack
        # ------------------------------------------------------------------ #
        lambda_sg = ec2.SecurityGroup.from_security_group_id(
            self,
            "LambdaSg",
            security_group_id=data_stack.lambda_sg_id,
        )

        # ------------------------------------------------------------------ #
        # Lambda environment variables
        # ------------------------------------------------------------------ #
        lambda_env: dict[str, str] = {
            # Database
            "TRADING_DATABASE_SECRET_ARN": data_stack.db_secret_arn,
            "TRADING_DB_HOST": data_stack.db_instance_endpoint,
            "TRADING_DB_PORT": data_stack.db_instance_port,
            "TRADING_DB_NAME": "trading",
            # Auth
            "JWT_SECRET_KEY_ARN": jwt_secret.secret_arn,
            # App metadata
            "APP_ENV": config.stage,
            # CORS
            "ALLOWED_ORIGINS": ",".join(config.allowed_origins),
            # Prevent matplotlib GUI errors in Lambda (no display)
            "MPLBACKEND": "Agg",
        }

        # ------------------------------------------------------------------ #
        # Lambda (Docker image function)
        # Heavy native deps (numpy, statsmodels, scikit-learn, bcrypt)
        # exceed the 250 MB zip limit — Docker image Lambda has a 10 GB limit.
        # ------------------------------------------------------------------ #
        fn_kwargs: dict = dict(
            function_name=f"options-lab-api{config.stack_suffix}",
            description=f"OptionsLab FastAPI backend — {config.stage}",
            code=lambda_.DockerImageCode.from_image_asset(
                directory=_REPO_ROOT,
                file="Dockerfile.lambda",
                exclude=[
                    "venv", ".venv", ".git", "cdk.out",
                    "web/node_modules", "web/.next",
                    "tests", "infrastructure", "*.db",
                ],
            ),
            memory_size=config.lambda_memory_mb,
            timeout=Duration.seconds(config.lambda_timeout_s),
            vpc=data_stack.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
            ),
            security_groups=[lambda_sg],
            environment=lambda_env,
            log_retention=_log_retention(config.log_retention_days),
        )
        if config.lambda_reserved_concurrency is not None:
            fn_kwargs["reserved_concurrent_executions"] = (
                config.lambda_reserved_concurrency
            )

        fn = lambda_.DockerImageFunction(self, "TradingApiFunction", **fn_kwargs)

        # ------------------------------------------------------------------ #
        # IAM: grant Lambda read access to both secrets
        # ------------------------------------------------------------------ #
        jwt_secret.grant_read(fn)
        fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                resources=[data_stack.db_secret_arn],
            )
        )

        # ------------------------------------------------------------------ #
        # HTTP API Gateway v2
        # CORS is handled by FastAPI middleware so no APIGW-level CORS is set
        # (duplicate headers would break preflight responses).
        # ------------------------------------------------------------------ #
        http_api = apigwv2.HttpApi(
            self,
            "TradingHttpApi",
            api_name=f"options-lab-api{config.stack_suffix}",
            description=f"OptionsLab FastAPI backend — {config.stage}",
        )

        lambda_integration = integrations.HttpLambdaIntegration(
            "LambdaIntegration",
            fn,
            payload_format_version=apigwv2.PayloadFormatVersion.VERSION_2_0,
        )

        for path in ("/", "/{proxy+}"):
            http_api.add_routes(
                path=path,
                methods=[apigwv2.HttpMethod.ANY],
                integration=lambda_integration,
            )

        # ------------------------------------------------------------------ #
        # Outputs
        # ------------------------------------------------------------------ #
        self.api_url: str = http_api.api_endpoint

        CfnOutput(
            self,
            "ApiUrl",
            value=self.api_url,
            description="API Gateway URL — set as NEXT_PUBLIC_API_URL in Amplify",
        )
        CfnOutput(self, "FunctionName", value=fn.function_name)
        CfnOutput(self, "JwtSecretArn", value=jwt_secret.secret_arn)
        CfnOutput(self, "Stage", value=config.stage)
