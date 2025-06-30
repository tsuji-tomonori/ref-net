from typing import Any, Self

import aws_cdk as cdk
from aws_cdk import aws_s3 as s3
from constructs import Construct

from src.model.env import Env


class S3Construct(Construct):
    """S3 bucket construct for static hosting and thumbnails."""

    def __init__(
        self: Self,
        scope: Construct,
        construct_id: str,
        environment: Env,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """Initialize S3 construct.

        Args:
            scope: The scope in which to define this construct
            construct_id: The scoped construct ID
            environment: Environment name (dev/prod)
            **kwargs: Additional keyword arguments
        """
        super().__init__(scope, construct_id, **kwargs)

        self.env = environment

        # Create S3 bucket
        self.bucket = s3.Bucket(
            self,
            "Bucket",
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            removal_policy=self.env.removal_policy(),
        )

        # Output bucket name
        cdk.CfnOutput(
            self,
            "BucketArn",
            value=self.bucket.bucket_arn,
            description=f"S3 bucket ARN for {self.env} environment",
        )
