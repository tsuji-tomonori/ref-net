import enum

from aws_cdk import RemovalPolicy, aws_logs
from aws_cdk import aws_lambda as lambda_


class Env(enum.Enum):
    """Environment enum for different deployment environments."""

    LOCAL = "local"
    DEV = "dev"
    STG = "stg"
    PRD = "prd"

    @classmethod
    def from_string(cls, value: str) -> "Env":
        """Convert a string to an Environment enum."""
        return cls(value.lower())

    @property
    def camel_case(self) -> str:
        """Get the camel case representation of the environment."""
        return self.name[0].upper() + self.name[1:].lower()

    def is_production(self) -> bool:
        """Check if the environment is production."""
        return self == Env.PRD or self == Env.STG

    def removal_policy(self) -> RemovalPolicy:
        """Get the removal policy for the environment."""
        return RemovalPolicy.RETAIN if self.is_production() else RemovalPolicy.DESTROY

    def retention_days(self) -> aws_logs.RetentionDays:
        """Get the log retention days for the environment."""
        return (
            aws_logs.RetentionDays.THREE_MONTHS
            if self.is_production()
            else aws_logs.RetentionDays.ONE_MONTH
        )

    def system_log_level(self) -> lambda_.SystemLogLevel:
        """Get the system log level for the environment."""
        return (
            lambda_.SystemLogLevel.WARN
            if self.is_production()
            else lambda_.SystemLogLevel.INFO
        )

    def application_log_level(self) -> lambda_.ApplicationLogLevel:
        """Get the application log level for the environment."""
        return (
            lambda_.ApplicationLogLevel.ERROR
            if self.is_production()
            else lambda_.ApplicationLogLevel.INFO
        )
