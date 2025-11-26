# List IPs for Digital Ocean droplets in a given environment.
#
# Usage:
#   ```sh
#   uv run python -m \
#     digitalocean_deployment_orchestrator.list_droplet_IPs [-h] {test,live}
#       [--tag sometag]
#   ```
#
# Prerequisites:
#   Binaries that should be available locally:
#     - [ ] uv <https://docs.astral.sh/uv>
#   Data that must be available to this script:
#     - [ ] A Digital Ocean token stored in env. var. `$DIGITALOCEAN__TOKEN`

import argparse
from uuid import UUID

from pydo import Client as DO_Client

from digitalocean_deployment_orchestrator.types import Environment
from digitalocean_deployment_orchestrator.types_DO import (
    DigitalOceanCredentials,
    DropletListResponse,
    DropletResponse,
    IPVersion,
)
from digitalocean_deployment_orchestrator.utils import (
    get_public_ip,
    get_wkid_from_tags,
)


def get_droplet_ips_for_env(
    do_client: DO_Client,
    env: Environment,
    *,
    version: IPVersion | None = None,
    required_tags: set[str] | None = None,
) -> dict[UUID, str]:
    if version is None:
        version = "v4"

    droplets_res: DropletListResponse = do_client.droplets.list(tag_name=env.tag)
    droplets: list[DropletResponse] = droplets_res["droplets"]

    addresses = {}
    for d in droplets:
        if required_tags and not required_tags.issubset(set(d.get("tags", []))):
            continue

        wkid = get_wkid_from_tags(d["tags"])
        ip = get_public_ip(d, version)
        if wkid is not None and ip is not None:
            addresses[wkid] = ip

    return addresses


def main(
    *, do_client: DO_Client, env: Environment, required_tags: set[str] | None = None
):
    for ip in get_droplet_ips_for_env(
        do_client, env, required_tags=required_tags
    ).values():
        print(ip)  # noqa: T201 <https://docs.astral.sh/ruff/rules/print>


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "env",
        type=Environment,
        choices=list(Environment),
        help="Environment to run against",
    )
    parser.add_argument(
        "--tag",
        action="append",
        default=None,
        help="Tag to match Droplets against. May be supplied multiple times.",
    )

    args = parser.parse_args()

    env = args.env
    required_tags = set(args.tag) if args.tag else None

    do_creds = DigitalOceanCredentials.from_env()
    do_client = DO_Client(do_creds.digitalocean__token)
    main(do_client=do_client, env=env, required_tags=required_tags)
