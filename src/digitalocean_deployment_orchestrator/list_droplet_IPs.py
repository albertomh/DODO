# List IPs for Digital Ocean droplets in a given environment.
#
# Usage:
#   ```sh
#   uv run python -m \
#     digitalocean_deployment_orchestrator.list_droplet_IPs [-h] {test,live}
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
    do_client: DO_Client, env: Environment, version: IPVersion | None = None
) -> dict[UUID, str]:
    if version is None:
        version = "v4"

    droplets_res: DropletListResponse = do_client.droplets.list(tag_name=env.tag)
    droplets: list[DropletResponse] = droplets_res["droplets"]

    addresses = {}
    for d in droplets:
        wkid = get_wkid_from_tags(d["tags"])
        ip = get_public_ip(d, version)
        if wkid is not None and ip is not None:
            addresses[wkid] = ip

    return addresses


def main(*, do_client: DO_Client, env: Environment):
    for ip in get_droplet_ips_for_env(do_client, env).values():
        print(ip)  # noqa: T201 <https://docs.astral.sh/ruff/rules/print>


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "env",
        type=Environment,
        choices=list(Environment),
        help="Environment to run against",
    )
    args = parser.parse_args()
    env = args.env

    do_creds = DigitalOceanCredentials.from_env()
    do_client = DO_Client(do_creds.digitalocean__token)
    main(do_client=do_client, env=env)
