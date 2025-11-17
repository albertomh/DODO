# Types specific to Cloudflare for use in DODO environment blueprints.

from dataclasses import dataclass
from typing import TypedDict

from digitalocean_deployment_orchestrator.types import EnvVarDataClass


@dataclass(frozen=True)
class CloudflareCredentials(EnvVarDataClass):
    cloudflare__token: str


class DNSRecord(TypedDict):
    zone_id: str
    record_name: str
    proxied: bool
