import argparse
import copy
import json
import pprint
from collections.abc import Mapping
from pathlib import Path
from uuid import UUID

import structlog
from cloudflare import Cloudflare
from cloudflare.types.dns import (
    AAAARecord,
    ARecord,
    CNAMERecord,
    MXRecord,
    NSRecord,
    PTRRecord,
    SRVRecordParam,
    TXTRecord,
)
from cloudflare.types.zones.zone import Zone
from pydo import Client as DO_Client

from digitalocean_deployment_orchestrator.infra.types import (
    EnvironmentBlueprint,
)
from digitalocean_deployment_orchestrator.infra.utils import import_module_from_path
from digitalocean_deployment_orchestrator.list_droplet_IPs import get_droplet_ips_for_env
from digitalocean_deployment_orchestrator.logging import configure_logging
from digitalocean_deployment_orchestrator.types import Environment
from digitalocean_deployment_orchestrator.types_cloudflare import (
    CloudflareCredentials,
    DNSRecord,
)
from digitalocean_deployment_orchestrator.types_DO import (
    DigitalOceanCredentials,
    DropletCreateResponse,
    DropletListResponse,
    DropletRequest,
    DropletResponse,
)
from digitalocean_deployment_orchestrator.utils import (
    get_wkid_from_tags,
)

LOGGER = structlog.get_logger()
configure_logging()


def load_environment_blueprint(
    blueprints_dir: Path, env: Environment
) -> EnvironmentBlueprint:
    """Load the blueprint for a given environment and ensure resources are tagged."""

    def _tag_resources(blueprint: EnvironmentBlueprint) -> EnvironmentBlueprint:
        bp = copy.deepcopy(blueprint)
        bp_env = bp["environment"]

        droplets = bp["droplets"]
        for d in droplets:
            env_tag = f"env:{bp_env.value}"
            wkid_tag = f"wkid:{d['well_known_uuid']}"
            d["tags"].extend([env_tag, wkid_tag])

        return bp

    env_blueprints = []

    for module_path in blueprints_dir.iterdir():
        if (
            not module_path.is_file()
            or module_path.suffix != ".py"
            or module_path.stem == "__init__"
        ):
            continue

        module = import_module_from_path(module_path)

        if not hasattr(module, "BLUEPRINT"):
            LOGGER.warning(
                "Skipping module with no BLUEPRINT", module_path=str(module_path)
            )
            continue

        bp = module.BLUEPRINT

        if bp["environment"] == env:
            env_blueprints.append(bp)
            LOGGER.info(
                "Loaded blueprint",
                module_path=str(module_path),
                environment=bp["environment"].value,
            )

    if not env_blueprints:
        raise RuntimeError(
            f"No blueprints found for env:{env.value} in 'infra/env_blueprints/'"
        )

    if len(env_blueprints) != 1:
        raise ValueError(f"Multiple blueprints found for env:{env.value}")

    bp = _tag_resources(env_blueprints[0])
    return bp


def manage_droplets(
    is_dry_run: bool,
    do_client: DO_Client,
    env: Environment,
    blueprint_droplets: list[DropletRequest],
):
    actual_droplets_res: DropletListResponse = do_client.droplets.list(tag_name=env.tag)
    actual_droplets: list[DropletResponse] = actual_droplets_res["droplets"]
    needed_droplets: list[DropletRequest] = copy.deepcopy(blueprint_droplets)
    actual_droplet_uuids = {get_wkid_from_tags(d["tags"]) for d in actual_droplets}
    needed_droplet_uuids = {get_wkid_from_tags(d["tags"]) for d in needed_droplets}

    existing = actual_droplet_uuids & needed_droplet_uuids
    to_create = needed_droplet_uuids - actual_droplet_uuids
    to_destroy = actual_droplet_uuids - needed_droplet_uuids

    LOGGER.info(
        "Droplet comparison",
        existing=len(existing),
        to_create=len(to_create),
        to_destroy=len(to_destroy),
    )

    if not to_create and not to_destroy:
        LOGGER.info(
            "Droplets in environment already match blueprint", environment=env.value
        )
        return

    def _create_droplet(droplet_req: DropletRequest):
        try:
            # deep copy + convert UUIDs
            safe_req = json.loads(json.dumps(droplet_req, default=str))
            res: DropletCreateResponse = do_client.droplets.create(body=safe_req)
        except Exception as err:
            LOGGER.error("Error creating Droplet", err=str(err))
            raise err
        else:
            wkid = get_wkid_from_tags(droplet_req["tags"])
            LOGGER.info("Created Droplet", wkid=str(wkid), id=res["droplet"]["id"])

    if to_create:
        droplets_to_create = [
            d for d in needed_droplets if d["well_known_uuid"] in to_create
        ]
        LOGGER.info(
            "Droplets to create",
            droplets={d["name"]: str(d["well_known_uuid"]) for d in droplets_to_create},
        )
        for droplet_req in droplets_to_create:
            redacted_droplet = {
                k: (v if k != "user_data" else "***REDACTED***")
                for k, v in droplet_req.items()
            }
            if is_dry_run:
                print("Would create Droplet:")  # noqa: T201
                pprint.pp(redacted_droplet)
            else:
                wkid = get_wkid_from_tags(droplet_req["tags"])
                if wkid in to_create:
                    _create_droplet(droplet_req)

    def _destroy_droplet(droplet_id: int, wkid: UUID):
        try:
            do_client.droplets.destroy(droplet_id=droplet_id)
        except Exception as err:
            LOGGER.error("Failed to destroy Droplet", err=str(err))
            raise err
        else:
            LOGGER.info("Destroyed Droplet", wkid=str(wkid), id=droplet_id)

    if to_destroy:
        droplets_to_destroy = [
            d for d in actual_droplets if get_wkid_from_tags(d["tags"]) in to_destroy
        ]
        LOGGER.info(
            "Droplets to destroy",
            droplets={
                d["name"]: str(get_wkid_from_tags(d["tags"])) for d in droplets_to_destroy
            },
        )
        for droplet in droplets_to_destroy:
            if is_dry_run:
                print("Would destroy Droplet:")  # noqa: T201
                pprint.pp(droplet)
            else:
                wkid = get_wkid_from_tags(droplet["tags"])
                if wkid in to_destroy:
                    _destroy_droplet(droplet["id"], wkid)


def manage_cloudflare_dns(
    is_dry_run: bool,
    do_client: DO_Client,
    cf_client: Cloudflare,
    env: Environment,
    blueprint_dns_records: list[DNSRecord],
):
    # { zone_name: zone_id } eg. { 'example.com': '12ab...0789' }
    zone_cache: dict[str, str] = {}
    # { zone_id: list of DNS records }
    zone_records_cache: dict[
        str,
        list[
            ARecord
            | AAAARecord
            | CNAMERecord
            | MXRecord
            | TXTRecord
            | NSRecord
            | SRVRecordParam
            | PTRRecord
        ],
    ] = {}

    for dns in blueprint_dns_records:
        dns_content = dns.get("content")
        if isinstance(dns_content, Mapping) and "droplet_wkid" in dns_content:
            # handle when dns_content is an `IPAddressForDroplet` TypedDict
            droplet_ips_for_env = get_droplet_ips_for_env(do_client, env)
            wkid = dns_content["droplet_wkid"]
            if wkid not in droplet_ips_for_env:
                LOGGER.warning(
                    "Could not match wkid to running droplet",
                    droplet_wkid=str(wkid),
                )
                continue
            dns["content"] = droplet_ips_for_env[wkid]

        cf_zone_name = dns["cf_zone_name"]
        if cf_zone_name not in zone_cache:
            try:
                zone: Zone = cf_client.zones.list(name=cf_zone_name).result[0]
            except IndexError:
                err_msg = f"Zone {cf_zone_name} not found in Cloudflare"
                raise RuntimeError(err_msg) from None
            if not zone:
                err_msg = f"Zone {cf_zone_name} not found in Cloudflare"
                raise RuntimeError(err_msg)
            zone_cache[cf_zone_name] = zone.id

        zone_id = zone_cache[cf_zone_name]

        if zone_id not in zone_records_cache:
            zone_records_cache[zone_id] = cf_client.dns.records.list(
                zone_id=zone_id
            ).result

        fqdn = cf_zone_name if dns["name"] == "@" else f"{dns['name']}.{cf_zone_name}"
        cur_dns_records = [
            record
            for record in zone_records_cache[zone_id]
            if record.name == fqdn and record.type == dns["type"]
        ]

        new_record_data = {
            "zone_id": zone_id,
            "type": dns["type"],
            "name": dns["name"],
            "content": dns["content"],
            "proxied": dns["proxied"],
        }
        if not dns["proxied"]:
            new_record_data["ttl"] = dns["ttl"]

        if cur_dns_records:
            if is_dry_run:
                LOGGER.info("Would update DNS record", name=dns["name"], type=dns["type"])
            else:
                update_record_data = {
                    "dns_record_id": cur_dns_records[0].id,
                    **new_record_data,
                }
                cf_client.dns.records.update(**update_record_data)
                LOGGER.info("Updated DNS record", name=dns["name"], type=dns["type"])
        else:
            if is_dry_run:
                LOGGER.info("Would create DNS record", name=dns["name"], type=dns["type"])
            else:
                cf_client.dns.records.create(**new_record_data)
                LOGGER.info("Created DNS record", name=dns["name"], type=dns["type"])


def apply(
    is_dry_run: bool,
    do_client: DO_Client,
    cloudflare_client: Cloudflare,
    blueprints_dir: Path,
    env: Environment,
):
    blueprint: EnvironmentBlueprint = load_environment_blueprint(blueprints_dir, env)

    manage_droplets(is_dry_run, do_client, env, blueprint["droplets"])

    manage_cloudflare_dns(
        is_dry_run,
        do_client,
        cloudflare_client,
        env,
        blueprint["dns"],
    )


if __name__ == "__main__":

    def _dir_path(string):
        dir_path = Path(string)
        if dir_path.is_dir():
            return dir_path
        else:
            raise NotADirectoryError(string)

    parser = argparse.ArgumentParser()
    parser.add_argument("blueprints_dir", type=_dir_path)
    parser.add_argument(
        "env",
        type=Environment,
        choices=list(Environment),
        help="Environment to run against",
    )
    parser.add_argument(
        "--no-dry-run",
        required=False,
        action="store_true",
        help="Actually apply blueprint to environment",
    )
    args = parser.parse_args()
    blueprints_dir = args.blueprints_dir
    env = args.env
    is_dry_run = not args.no_dry_run
    LOGGER.info("Running DODO", environment=env.value)

    do_creds = DigitalOceanCredentials.from_env()
    do_client = DO_Client(do_creds.digitalocean__token)
    cloudflare_creds = CloudflareCredentials.from_env()
    cloudflare_client = Cloudflare(api_token=cloudflare_creds.cloudflare__token)
    apply(is_dry_run, do_client, cloudflare_client, blueprints_dir, env)
