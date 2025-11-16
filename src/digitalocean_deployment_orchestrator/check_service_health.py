import argparse
import json
import logging
import ssl
import sys
import time
import urllib.request
from typing import Literal

from pydo import Client as DO_Client

from digitalocean_deployment_orchestrator.list_droplet_IPs import get_droplet_ips_for_env
from digitalocean_deployment_orchestrator.types import Environment
from digitalocean_deployment_orchestrator.types_DO import DigitalOceanCredentials
from digitalocean_deployment_orchestrator.utils import set_up_basic_logging

LOG = logging.getLogger(__name__)


def service_is_healthy(
    *,
    protocol: Literal["http", "https"] = "https",
    ip="127.0.0.1",
    port="80",
    health_endpoint: str | None = None,
    max_attempts: int = 10,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
) -> bool:
    if health_endpoint is None:
        health_endpoint = "/-/health/"

    socket_address = ip
    if port != "80":
        socket_address = f"{ip}:{port}"
    url = f"{protocol}://{socket_address}{health_endpoint}"
    LOG.info("checking health of service '%s'", url)

    retry_delay = initial_delay
    for attempt in range(max_attempts):
        try:
            context = ssl._create_unverified_context()  # noqa: S323 suspicious-unverified-context-usage
            res = urllib.request.urlopen(url, context=context)  # noqa S310 suspicious-url-open-usage
            if res.status != 200:
                return False
            res_json = json.loads(res.read())
            return res_json["healthy"]
        except json.JSONDecodeError:
            raise
        except (urllib.error.URLError, ConnectionRefusedError):
            if attempt < max_attempts - 1:
                time.sleep(retry_delay)
                retry_delay *= backoff_factor
                continue
            raise
    return False


def main(*, do_client: DO_Client, env: Environment):
    unhealthy_services = []
    for ip in get_droplet_ips_for_env(do_client, env).values():
        try:
            if service_is_healthy(ip=ip):
                LOG.info("service '%s' is healthy", ip)
            else:
                LOG.error("service '%s' is not healthy", ip)
                unhealthy_services.append(ip)
        except RuntimeError as e:
            LOG.error(str(e))
            unhealthy_services.append(ip)

        if unhealthy_services:
            LOG.error(
                "found '%s' unhealthy services: [%s]",
                str(len(unhealthy_services)),
                ",".join(unhealthy_services),
            )
            sys.exit(1)


if __name__ == "__main__":
    set_up_basic_logging()

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
