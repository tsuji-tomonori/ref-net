from typing import Any, Self

from pathlib import Path

import aws_cdk as cdk
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from constructs import Construct
from src.model.env import Env
from src.model.project import Project


class LambdaConstruct(Construct):
    """Lambda function construct for FastAPI backend."""

    def __init__(
        self: Self,
        scope: Construct,
        construct_id: str,
        target: str,
        environment: Env,
        project: Project,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """Initialize Lambda construct.

        Args:
            scope: The scope in which to define this construct
            construct_id: The scoped construct ID
            environment: Environment name (dev/prod)
            project: Project metadata
            **kwargs: Additional keyword arguments
        """
        super().__init__(scope, construct_id, **kwargs)

        self.env = environment

        code_path = Path(__file__).parent.parent.parent / "package" / "batch" / target

        # Create Lambda function
        self.function = lambda_.Function(
            self,
            "Function",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="main.handler",
            code=lambda_.Code.from_asset(str(code_path)),
            memory_size=512,
            timeout=cdk.Duration.seconds(30),
            logging_format=lambda_.LoggingFormat.JSON,
            system_log_level_v2=environment.system_log_level(),
            application_log_level_v2=environment.application_log_level(),
            description=project.description,
            environment={
                "ENV_NAME": environment.name,
                "POWERTOOLS_SERVICE_NAME": project.name,
                "POWERTOOLS_METRICS_NAMESPACE": project.name,
                "PROJECT_MAJOR_VERSION": project.major_version,
                "PROJECT_SEMANTIC_VERSION": project.semantic_version,
            },
        )

        # Create log group with retention
        self.log_group = logs.LogGroup(
            self,
            "LogGroup",
            log_group_name=f"/aws/lambda/{self.function.function_name}",
            retention=environment.retention_days(),
            removal_policy=environment.removal_policy(),
        )

        # Output function ARN
        cdk.CfnOutput(
            self,
            "FunctionArn",
            value=self.function.function_arn,
            description=f"Lambda function ARN for {self.env} environment",
        )

        cdk.CfnOutput(
            self,
            "LogGroupArn",
            value=self.log_group.log_group_arn,
            description=f"Log group ARN for {self.env} environment",
        )
