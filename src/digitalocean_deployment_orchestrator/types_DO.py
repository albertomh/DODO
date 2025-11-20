# Types specific to Digital Ocean for use in DODO environment blueprints.

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, NotRequired, TypedDict
from uuid import UUID

from digitalocean_deployment_orchestrator.types import EnvVarDataClass


@dataclass(frozen=True)
class DigitalOceanCredentials(EnvVarDataClass):
    digitalocean__token: str


class MetaApiRes(TypedDict):
    total: int


class DORegion(StrEnum):
    LONDON1 = "lon1"


class DropletSize(StrEnum):
    """
    <https://www.digitalocean.com/pricing/droplets>
    <https://www.nist.gov/pml/owm/metric-si-prefixes>
    """

    BASIC_YOCTO = "s-1vcpu-512mb-10gb"  # $4/mo
    BASIC_ZEPTO = "s-1vcpu-1gb"  # $6/mo


class DropletImage(StrEnum):
    DEBIAN_12_X64 = "debian-12-x64"
    DEBIAN_13_X64 = "debian-13-x64"
    UBUNTU_2404_X64 = "ubuntu-24-04-x64"
    UBUNTU_2504_X64 = "ubuntu-25-04-x64"


class BaseDroplet(TypedDict):
    name: str
    tags: list[str]
    vpc_uuid: str


class DropletRequest(BaseDroplet):
    """Data object used to request the creation of a Droplet.

    <https://docs.digitalocean.com/reference/api/digitalocean/#tag/Droplets/operation/droplets_create>
    """

    region: DORegion
    size: DropletSize
    image: DropletImage
    # the fingerprint(s) of SSH keys to embed in the Droplet's root account
    ssh_keys: list[str]
    backups: NotRequired[bool]
    ipv6: NotRequired[bool]
    monitoring: NotRequired[bool]
    # `user_data` should be the contents of a 'cloud-config' file
    # <https://www.digitalocean.com/community/tutorials/an-introduction-to-cloud-config-scripting>
    user_data: str
    well_known_uuid: UUID


IPVersion = Literal["v4", "v6"]


class NetworkInfo(TypedDict):
    ip_address: str
    netmask: str
    gateway: str
    type: IPVersion


class DropletNetworks(TypedDict):
    v4: list[NetworkInfo]
    v6: list[NetworkInfo]


DropletStatus = Literal["new", "active", "off", "archive"]


class DropletResponse(BaseDroplet):
    """Data object received as a response from Droplet-related APIs.

    <https://docs.digitalocean.com/reference/api/digitalocean/#tag/Droplets>
    """

    id: int
    status: DropletStatus
    created_at: str
    networks: DropletNetworks


class DropletCreateResponse(TypedDict):
    droplet: DropletResponse
    links: dict


class DropletListResponse(TypedDict):
    droplets: list[DropletResponse]
    links: dict
    meta: MetaApiRes


class IPAddressForDroplet(TypedDict):
    """Use in env. blueprints to indirectly point to a Droplet's IP without revealing it.

    When an `IPAddressForDroplet` is detected by `apply.manage_cloudflare_dns()` as the
    value of a `DNSRecord.content`, this object will be replaced with an IP address.
    """

    droplet_wkid: UUID
