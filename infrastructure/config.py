"""Per-environment configuration for all CDK stacks.

Usage in app.py:
    stage = app.node.try_get_context("stage") or "dev"
    config = get_env_config(stage, account=..., region=...)

Selecting a stage:
    cdk deploy --all --context stage=dev
    cdk deploy --all --context stage=staging
    cdk deploy --all --context stage=production

All cost/size/retention values can be overridden per deployment by modifying
the dataclass returned from get_env_config(), or by subclassing.
"""

from dataclasses import dataclass, field

VALID_STAGES = ("dev", "staging", "production")


@dataclass
class EnvironmentConfig:
    """All tunable parameters for a deployment stage.

    Attributes
    ----------
    stage:
        One of 'dev', 'staging', 'production'.
    account:
        AWS account ID string; None → CDK_DEFAULT_ACCOUNT env var.
    region:
        AWS region string; None → CDK_DEFAULT_REGION env var.

    --- Network ---
    nat_gateways:
        Number of NAT gateways.  0 = no NAT (cheapest; Lambda must be in a
        public subnet or VPC endpoints must be added).  1 is the minimum for
        Lambda in a private subnet to reach the internet.

    --- Database (RDS PostgreSQL) ---
    db_instance_class:
        RDS instance type string, e.g. 't3.micro', 't3.small', 't3.medium'.
    db_allocated_gb:
        Initial storage allocation in GB (minimum 20).
    db_max_allocated_gb:
        Storage autoscaling ceiling in GB.
    db_multi_az:
        Enable Multi-AZ standby instance (doubles RDS cost; recommended for prod).
    db_deletion_protection:
        Prevent accidental instance deletion via console/CLI.
    db_removal_policy:
        'DESTROY' | 'SNAPSHOT' | 'RETAIN'.
        'SNAPSHOT' keeps a final snapshot; 'RETAIN' leaves the instance alive.

    --- Lambda ---
    lambda_memory_mb:
        Lambda allocated memory.  CPU scales proportionally.
    lambda_timeout_s:
        Maximum Lambda execution duration in seconds.
    lambda_reserved_concurrency:
        Fixed concurrency cap; None = unreserved (shares account pool).

    --- Observability ---
    log_retention_days:
        CloudWatch log group retention.  Must be one of:
        1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545,
        731, 1096, 1827, 2192, 2557, 2922, 3288, 3653.

    --- Security / lifecycle ---
    allowed_origins:
        CORS allowed origins list.  ['*'] permits any origin (suitable when
        auth is JWT-based).  For stricter deployments set to the Amplify URL
        or custom domain after the first deploy.
    """

    stage: str
    account: str | None = None
    region: str | None = None

    # Network
    nat_gateways: int = 1

    # Database
    db_instance_class: str = "t3.micro"
    db_allocated_gb: int = 20
    db_max_allocated_gb: int = 100
    db_multi_az: bool = False
    db_deletion_protection: bool = False
    db_removal_policy: str = "SNAPSHOT"  # DESTROY | SNAPSHOT | RETAIN

    # Lambda
    lambda_memory_mb: int = 1024
    lambda_timeout_s: int = 30
    lambda_reserved_concurrency: int | None = None

    # Observability
    log_retention_days: int = 14

    # Security
    allowed_origins: list[str] = field(default_factory=lambda: ["*"])

    # ------------------------------------------------------------------ #
    # Derived helpers
    # ------------------------------------------------------------------ #

    @property
    def is_production(self) -> bool:
        return self.stage == "production"

    @property
    def stack_suffix(self) -> str:
        """Empty for production (clean names), '-<stage>' for others."""
        return "" if self.is_production else f"-{self.stage}"

    @property
    def secret_prefix(self) -> str:
        """Secrets Manager name prefix scoped to this stage."""
        return f"options-lab/{self.stage}"


# --------------------------------------------------------------------------- #
# Pre-built configurations
# --------------------------------------------------------------------------- #

def _dev(account: str | None, region: str | None) -> EnvironmentConfig:
    return EnvironmentConfig(
        stage="dev",
        account=account,
        region=region,
        nat_gateways=1,
        db_instance_class="t3.micro",
        db_allocated_gb=20,
        db_max_allocated_gb=50,
        db_multi_az=False,
        db_deletion_protection=False,
        db_removal_policy="DESTROY",   # fast teardown during development
        lambda_memory_mb=512,
        lambda_timeout_s=30,
        log_retention_days=7,
        allowed_origins=["*"],
    )


def _staging(account: str | None, region: str | None) -> EnvironmentConfig:
    return EnvironmentConfig(
        stage="staging",
        account=account,
        region=region,
        nat_gateways=1,
        db_instance_class="t3.micro",
        db_allocated_gb=20,
        db_max_allocated_gb=100,
        db_multi_az=False,
        db_deletion_protection=False,
        db_removal_policy="SNAPSHOT",  # keep data between redeployments
        lambda_memory_mb=1024,
        lambda_timeout_s=30,
        log_retention_days=30,
        allowed_origins=["*"],
    )


def _production(account: str | None, region: str | None) -> EnvironmentConfig:
    return EnvironmentConfig(
        stage="production",
        account=account,
        region=region,
        nat_gateways=1,
        db_instance_class="t3.small",  # bump for production load
        db_allocated_gb=20,
        db_max_allocated_gb=200,
        db_multi_az=True,              # standby replica for HA
        db_deletion_protection=True,
        db_removal_policy="RETAIN",    # never auto-delete production data
        lambda_memory_mb=1024,
        lambda_timeout_s=30,
        log_retention_days=90,
        allowed_origins=["*"],         # restrict to Amplify URL post-deploy if desired
    )


_FACTORY = {
    "dev": _dev,
    "staging": _staging,
    "production": _production,
}


def get_env_config(
    stage: str,
    *,
    account: str | None = None,
    region: str | None = None,
) -> EnvironmentConfig:
    """Return the EnvironmentConfig for the given stage.

    Parameters
    ----------
    stage:
        Deployment stage: 'dev', 'staging', or 'production'.
    account:
        AWS account ID (from CDK context or CDK_DEFAULT_ACCOUNT).
    region:
        AWS region (from CDK context or CDK_DEFAULT_REGION).

    Raises
    ------
    ValueError
        If stage is not one of the valid values.
    """
    if stage not in VALID_STAGES:
        raise ValueError(
            f"Unknown stage '{stage}'. Valid values: {', '.join(VALID_STAGES)}"
        )
    return _FACTORY[stage](account, region)
