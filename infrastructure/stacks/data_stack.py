"""CDK stack: VPC and RDS PostgreSQL for the trading app."""

from aws_cdk import CfnOutput, RemovalPolicy, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_rds as rds
from constructs import Construct

from infrastructure.config import EnvironmentConfig

_REMOVAL_POLICY_MAP = {
    "DESTROY": RemovalPolicy.DESTROY,
    "SNAPSHOT": RemovalPolicy.SNAPSHOT,
    "RETAIN": RemovalPolicy.RETAIN,
}


class DataStack(Stack):
    """VPC + RDS PostgreSQL.

    Resources scale with the deployment stage:
      dev        — t3.micro, single-AZ, DESTROY removal policy
      staging    — t3.micro, single-AZ, SNAPSHOT removal policy
      production — t3.small, Multi-AZ, RETAIN + deletion protection
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: EnvironmentConfig,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        removal_policy = _REMOVAL_POLICY_MAP.get(
            config.db_removal_policy, RemovalPolicy.SNAPSHOT
        )

        # ------------------------------------------------------------------ #
        # VPC
        # ------------------------------------------------------------------ #
        vpc = ec2.Vpc(
            self,
            "TradingVpc",
            max_azs=2,
            nat_gateways=config.nat_gateways,
        )

        # Security group for RDS: allow inbound 5432 from within the VPC
        db_sg = ec2.SecurityGroup(
            self,
            "DbSg",
            vpc=vpc,
            description=f"Allow PostgreSQL from VPC ({config.stage})",
        )
        db_sg.add_ingress_rule(
            peer=ec2.Peer.ipv4(vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(5432),
            description="PostgreSQL from VPC",
        )

        # Security group for Lambda (stateful egress; Lambda initiates connections)
        lambda_sg = ec2.SecurityGroup(
            self,
            "LambdaSg",
            vpc=vpc,
            description=f"Security group for Trading API Lambda ({config.stage})",
        )

        # ------------------------------------------------------------------ #
        # RDS PostgreSQL
        # ------------------------------------------------------------------ #
        db = rds.DatabaseInstance(
            self,
            "TradingDb",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_16_4,
            ),
            instance_type=ec2.InstanceType(config.db_instance_class),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
            ),
            security_groups=[db_sg],
            credentials=rds.Credentials.from_generated_secret("postgres"),
            database_name="trading",
            allocated_storage=config.db_allocated_gb,
            max_allocated_storage=config.db_max_allocated_gb,
            multi_az=config.db_multi_az,
            deletion_protection=config.db_deletion_protection,
            removal_policy=removal_policy,
        )

        # ------------------------------------------------------------------ #
        # Outputs
        # ------------------------------------------------------------------ #
        self.db_secret_arn = db.secret.secret_arn
        self.db_instance_endpoint = db.instance_endpoint.hostname
        self.db_instance_port = str(db.instance_endpoint.port)
        self.vpc = vpc
        self.db_sg = db_sg
        self.lambda_sg_id = lambda_sg.security_group_id

        CfnOutput(self, "DbSecretArn", value=self.db_secret_arn)
        CfnOutput(self, "DbHost", value=self.db_instance_endpoint)
        CfnOutput(self, "DbPort", value=self.db_instance_port)
        CfnOutput(self, "DbName", value="trading")
        CfnOutput(self, "VpcId", value=vpc.vpc_id)
        CfnOutput(self, "DbSgId", value=db_sg.security_group_id)
        CfnOutput(self, "LambdaSgId", value=lambda_sg.security_group_id)
        for i, subnet in enumerate(vpc.private_subnets):
            CfnOutput(self, f"PrivateSubnetId{i}", value=subnet.subnet_id)
