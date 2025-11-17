from dataclasses import dataclass
from typing import TypedDict
from uuid import UUID

from digitalocean_deployment_orchestrator.types import Environment, EnvVarDataClass
from digitalocean_deployment_orchestrator.types_cloudflare import DNSRecord
from digitalocean_deployment_orchestrator.types_DO import DropletRequest


class DropletDNSRecord(TypedDict):
    droplet_wkid: UUID
    dns_record: DNSRecord


class EnvironmentBlueprint(TypedDict):
    environment: Environment
    droplets: list[DropletRequest]
    dns: list[DropletDNSRecord]


@dataclass(frozen=True)
class PostgresServerEnv(EnvVarDataClass):
    ssh__public_key: str
    postgres_db: str
    postgres_user: str
    postgres_password: str


@dataclass(frozen=True)
class AppServerEnv(EnvVarDataClass):
    ssh__public_key: str
