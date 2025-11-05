from dataclasses import dataclass
from typing import TypedDict

from digitalocean_deployment_orchestrator.types import Environment, EnvVarDataClass
from digitalocean_deployment_orchestrator.types_DO import DropletRequest


class EnvironmentBlueprint(TypedDict):
    environment: Environment
    droplets: list[DropletRequest]


@dataclass(frozen=True)
class PostgresServerEnv(EnvVarDataClass):
    ssh__public_key: str
    postgres_db: str
    postgres_user: str
    postgres_password: str


@dataclass(frozen=True)
class AppServerEnv(EnvVarDataClass):
    ssh__public_key: str
