# Types specific to Cloudflare for use in DODO environment blueprints.

from dataclasses import dataclass
from typing import Literal, TypedDict

from cloudflare.types.dns.ttl_param import TTLParam

from digitalocean_deployment_orchestrator.types import EnvVarDataClass
from digitalocean_deployment_orchestrator.types_DO import IPAddressForDroplet


@dataclass(frozen=True)
class CloudflareCredentials(EnvVarDataClass):
    cloudflare__token: str


class DNSRecord(TypedDict):
    cf_zone_name: str
    type: Literal["A", "AAAA", "CNAME", "MX", "TXT", "NS", "SOA", "PTR"]
    name: str
    content: str | IPAddressForDroplet
    ttl: TTLParam | None  # in seconds - do not set if `proxied` is True
    proxied: bool
