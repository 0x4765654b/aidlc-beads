"""Gorilla Troop configuration -- Bedrock model, AWS profile, runtime settings."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class BedrockConfig:
    """Configuration for Amazon Bedrock / Strands Agents integration."""

    aws_profile: str = field(
        default_factory=lambda: os.environ.get("AWS_PROFILE", "ai3_d")
    )
    aws_region: str = field(
        default_factory=lambda: os.environ.get("BEDROCK_REGION", "us-east-1")
    )
    model_id: str = field(
        default_factory=lambda: os.environ.get(
            "BEDROCK_MODEL_ID", "us.anthropic.claude-opus-4-6-v1"
        )
    )
    temperature: float = field(
        default_factory=lambda: float(os.environ.get("BEDROCK_TEMPERATURE", "0.1"))
    )
    max_tokens: int = field(
        default_factory=lambda: int(os.environ.get("BEDROCK_MAX_TOKENS", "4096"))
    )

    def create_boto_session(self):
        """Create a boto3 session using the configured AWS profile.

        Returns:
            A boto3.Session configured with the ai3_d profile.
        """
        import boto3

        return boto3.Session(
            profile_name=self.aws_profile,
            region_name=self.aws_region,
        )

    def create_bedrock_model(self):
        """Create a Strands BedrockModel using the configured settings.

        Returns:
            A BedrockModel instance ready for use with Strands Agent.
        """
        from strands.models import BedrockModel

        session = self.create_boto_session()
        return BedrockModel(
            model_id=self.model_id,
            boto_session=session,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )


@dataclass
class AgentMailConfig:
    """Configuration for MCP Agent Mail."""

    url: str = field(
        default_factory=lambda: os.environ.get(
            "AGENT_MAIL_URL", "http://localhost:8080"
        )
    )


@dataclass
class GorillaConfig:
    """Top-level configuration for the Gorilla Troop system."""

    bedrock: BedrockConfig = field(default_factory=BedrockConfig)
    agent_mail: AgentMailConfig = field(default_factory=AgentMailConfig)
    workspace_root: str = field(
        default_factory=lambda: os.environ.get(
            "GORILLA_WORKSPACE", os.getcwd()
        )
    )
    log_level: str = field(
        default_factory=lambda: os.environ.get("GORILLA_LOG_LEVEL", "INFO")
    )
    default_project_key: str = field(
        default_factory=lambda: os.environ.get("DEFAULT_PROJECT_KEY", "")
    )
    default_project_name: str = field(
        default_factory=lambda: os.environ.get("DEFAULT_PROJECT_NAME", "")
    )
    default_project_path: str = field(
        default_factory=lambda: os.environ.get("DEFAULT_PROJECT_PATH", "")
    )


# Singleton for convenience
_config: GorillaConfig | None = None


def get_config() -> GorillaConfig:
    """Get or create the global Gorilla Troop configuration."""
    global _config
    if _config is None:
        _config = GorillaConfig()
    return _config


def reset_config() -> None:
    """Reset the global configuration (for testing)."""
    global _config
    _config = None
