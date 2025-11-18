# Types specific to Cloudflare for use in DODO environment blueprints.

from dataclasses import dataclass
from typing import Literal, TypedDict

from digitalocean_deployment_orchestrator.types import EnvVarDataClass


@dataclass(frozen=True)
class CloudflareCredentials(EnvVarDataClass):
    cloudflare__token: str


class DNSRecord(TypedDict):
    zone_id: str
    type: Literal["A", "AAAA", "CNAME", "MX", "TXT", "NS", "SOA", "PTR"]
    name: str
    proxied: bool
