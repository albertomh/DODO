# Deploy a webapp from a container image by following a blue/green deployment strategy.
#
# Assumes that the underlying infrastructure (and associated binaries) have been
# configured by a blueprint (see `../infra/` & `../infra/apply.py`).
#
# Usage:
#   ```sh
#   # run bare to see help message & full list of arguments
#   uv run python -m blue_green_deploy
#   ```
#
# Prerequisites:
#   Binaries that should be available locally:
#     - [ ] uv <https://docs.astral.sh/uv>
#     - [ ] wget
#   Data that needs to be passed to this script:
#     - [ ] A *classic* GitHub PAT with scope `read:packages`
#     - [ ] The absolute path to a .env file for the container to use

import argparse
import dataclasses as dc
import logging
import subprocess
import sys
from datetime import datetime
from enum import StrEnum, auto
from pathlib import Path
from typing import TypedDict

from digitalocean_deployment_orchestrator.check_service_health import service_is_healthy
from digitalocean_deployment_orchestrator.utils import set_up_basic_logging

GHCR_BASE_URL = "ghcr.io"

DEPLOY_PACKAGE_DIR = Path(__file__).resolve().parents[1]

LOG = logging.getLogger(__name__)


class DockerContainerInfo(TypedDict):
    ID: str
    Names: str
    Ports: str


@dc.dataclass
class Args:
    ghcr_username: str
    gh_pat: str
    docker_image: str
    container_name: str
    env_file_path: str
    ssl_dir: Path
    nginx_conf_dir: Path


class PortColour(StrEnum):
    BLUE = "8000"
    GREEN = "8080"


class ServerColour(StrEnum):
    BLUE = auto()
    GREEN = auto()


def get_argument_parser() -> argparse.ArgumentParser:
    desc = (
        "Blue/green deployment for Dockerised web apps\n\n"
        "Spins up a new webapp container, waits for it to be healthy,\n"
        "has nginx forward requests to the new one and winds down the\n"
        "old container."
    )

    parser = argparse.ArgumentParser(
        prog=Path(__file__).name,
        usage="uv run python -m blue_green_deploy",
        description=desc,
        epilog="Text at the bottom of help",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # arguments converted to more verbose names (`Args` dataclass) in main()
    parser.add_argument(
        "-u",
        "--ghcr-username",
        required=True,
        help="Username to authenticate against ghcr.io",
    )
    parser.add_argument(
        "-t",
        "--gh-pat",
        required=True,
        help="GitHub Personal Access Token. Must have scopes `repo`",
    )
    parser.add_argument(
        "-i",
        "--image",
        required=True,
        help="Path to a Docker image on ghcr.io eg. `albertomh/testdjereo:latest`",
    )
    parser.add_argument(
        "-n",
        "--name",
        required=True,
        help="Name for the container eg. `testdjereo`",
    )
    parser.add_argument(
        "-e",
        "--env-file",
        required=True,
        help="Absolute path to the .env file to use with the container",
    )
    parser.add_argument(
        "-s",
        "--ssl-dir",
        type=Path,
        default=Path("/etc/ssl"),
        help="Directory for certificates (default: /etc/ssl)",
    )
    parser.add_argument(
        "-x",
        "--nginx-conf-dir",
        type=Path,
        default=Path("/etc/nginx"),
        help="Directory for nginx configuration (default: /etc/nginx)",
    )

    return parser


def validate_args(args: Args):
    if not args.gh_pat.startswith(("github_pat_", "ghp_", "ghs_", "gho_")):
        raise ValueError("GitHub PAT [-t, --pat PAT] must start with 'github_pat_'")

    if "/" not in args.docker_image:
        raise ValueError("Docker image [-i, --image] must be the path to a ghcr.io image")


def create_docker_network(docker_network_name: str):
    existing_nets_res = subprocess.run(
        [  # noqa: S607 start-process-with-partial-path
            "docker",
            "network",
            "ls",
            "--format",
            "{{.Name}}",
        ],
        text=True,
        capture_output=True,
    )
    existing_nets = existing_nets_res.stdout.splitlines()
    if docker_network_name not in existing_nets:
        subprocess.run(
            [  # noqa: S607 start-process-with-partial-path
                "docker",
                "network",
                "create",
                docker_network_name,
            ],
        )


def log_in_to_github_container_registry(
    ghcr_username: str,
    gh_pat: str,
) -> None:
    result = subprocess.run(
        [  # noqa: S607 start-process-with-partial-path
            "docker",
            "login",
            "ghcr.io",
            "--username",
            ghcr_username,
            "--password",
            gh_pat,
        ],
        text=True,
        capture_output=True,
    )

    if result.returncode == 0:
        LOG.info("logged into ghcr.io")
    else:
        raise RuntimeError(
            "could not log into ghcr.io - check PAT passed as [-t, --gh-pat]"
        )


def new_static_volume_for_next(container_name: str) -> str:
    now = datetime.now().strftime("%Y%m%dT%H%M%S")
    volume_name = f"{container_name}_static_{now}"
    try:
        subprocess.run(
            [
                "docker",
                "volume",
                "create",
                volume_name,
            ],
            check=True,
        )
        LOG.info("created volume for static assets '%s'", volume_name)
        return volume_name
    except subprocess.CalledProcessError:
        raise RuntimeError(
            f"failed to create volume for static assets for '{container_name}'"
        ) from None


def get_containers_by_filter(filter_expr: str) -> list[DockerContainerInfo]:
    try:
        # eg. `3f...8d   <container_name>   0.0.0.0:8000->8000/tcp, :::8000->8000/tcp`
        result = subprocess.run(
            [
                "docker",
                "ps",
                "--format",
                "{{.ID}}\t{{.Names}}\t{{.Ports}}",
                "--filter",
                filter_expr,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        raise RuntimeError(
            "'docker ps' failed - check the Docker service is running"
        ) from None

    containers: list[DockerContainerInfo] = [
        {"ID": fields[0], "Names": fields[1], "Ports": fields[2]}
        for line in result.stdout.strip().splitlines()
        if (fields := line.split("\t"))
    ]
    return containers


def get_server_colours(container_name_prefix: str) -> tuple[ServerColour, ServerColour]:
    try:
        container_res = get_containers_by_filter(f"name=^{container_name_prefix}")
    except RuntimeError as e:
        raise e

    if len(container_res) == 0:
        LOG.warning("no running container found for '%s'", container_name_prefix)
        blue_port_map = f"{PortColour.BLUE.value}->{PortColour.BLUE.value}"
        cur_container: DockerContainerInfo = {
            "ID": "placeholderID",
            "Names": "placeholderName",
            "Ports": f"0.0.0.0:{blue_port_map}/tcp, :::{blue_port_map}/tcp",
        }
    elif len(container_res) == 1:
        cur_container = container_res[0]
    else:
        raise RuntimeError(f"found more than one '{container_name_prefix}' container")

    cur_port_mapping = cur_container["Ports"]
    if f"{PortColour.BLUE.value}->{PortColour.BLUE.value}" in cur_port_mapping:
        cur_colour = ServerColour.BLUE
        next_colour = ServerColour.GREEN
    elif f"{PortColour.GREEN.value}->{PortColour.GREEN.value}" in cur_port_mapping:
        cur_colour = ServerColour.GREEN
        next_colour = ServerColour.BLUE
    else:
        raise RuntimeError(
            f"could not establish next colour for '{container_name_prefix}' container"
        )

    LOG.info("current colour: %s, next colour: %s", cur_colour.value, next_colour.value)
    return cur_colour, next_colour


def create_next_app_container(
    *,
    docker_image: str,
    network_name: str,
    next_container_name: str,
    next_port: PortColour,
    next_static_volume: str,
    env_file_path: str,
) -> None:
    docker_image_path = f"{GHCR_BASE_URL}/{docker_image}"
    subprocess.run(
        ["docker", "image", "pull", docker_image_path],
        check=False,
    )

    subprocess.run(
        ["docker", "rm", "-f", next_container_name],
    )

    result = subprocess.run(
        [
            "docker",
            "run",
            "--detach",
            "--name",
            next_container_name,
            "--user",
            "root",
            "--env-file",
            env_file_path,
            "--env",
            f"PORT={next_port.value}",
            "--network",
            network_name,
            "--publish",
            f"{next_port.value}:{next_port.value}",
            "--volume",
            f"{next_static_volume}:/app/static",
            docker_image_path,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        LOG.info("created new container '%s'", next_container_name)
    else:
        LOG.error(result.stderr)
        raise RuntimeError(f"failed to create new container {next_container_name}")


def run_django_migrations_in_next_container(next_container_name: str):
    result = subprocess.run(
        ["docker", "exec", next_container_name, "python", "manage.py", "migrate"],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        LOG.info("ran Django migrations in container '%s'", next_container_name)
    else:
        LOG.error("'django migrate' stderr: %s", result.stderr)
        LOG.error(
            "error running Django migrations in container '%s'", next_container_name
        )


def create_self_signed_cert(ssl_dir: Path):
    cert_path = ssl_dir / "certs" / "selfsigned.crt"
    key_path = ssl_dir / "private" / "selfsigned.key"

    if cert_path.exists() and key_path.exists():
        LOG.info("existing self-signed certificate found")
        return

    LOG.info("no certificate found, generating self-signed certificate...")
    (ssl_dir / "private").mkdir(parents=True, exist_ok=True)
    (ssl_dir / "certs").mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            "sudo",
            "openssl",
            "req",
            "-x509",
            "-nodes",
            "-days",
            "365",
            "-newkey",
            "rsa:4096",
            "-keyout",
            str(key_path),
            "-out",
            str(cert_path),
            "-subj",
            "/CN=selfsigned",
        ],
        check=True,
    )

    subprocess.run(["sudo", "chmod", "600", str(key_path)], check=True)
    LOG.info("self-signed certificate created at '%s'", str(cert_path))


def update_nginx_proxy_target(next_port: PortColour, nginx_conf_dir: Path):
    debian_default = nginx_conf_dir / "sites-enabled" / "default"
    debian_default.unlink(missing_ok=True)

    template_path = DEPLOY_PACKAGE_DIR / "nginx" / "app.conf.template"
    live_path = nginx_conf_dir / "conf.d" / "app.conf"

    if not template_path.exists():
        raise FileNotFoundError(f"nginx template not found '{template_path}'")

    conf_text = template_path.read_text().replace("{{APP_PORT}}", next_port.value)
    live_path.write_text(conf_text)

    result = subprocess.run(
        ["sudo", "/usr/sbin/nginx", "-t"], capture_output=True, text=True
    )
    if result.returncode != 0:
        LOG.error("nginx config test failed:\n%s", result.stderr)
        raise RuntimeError("nginx config test failed")

    reload_res = subprocess.run(
        ["sudo", "systemctl", "reload", "nginx"], capture_output=True, text=True
    )
    if reload_res.returncode == 0:
        LOG.info("nginx reloaded and now proxies to port %s", next_port.value)
    else:
        LOG.error("failed to reload nginx: %s", reload_res.stderr)
        raise RuntimeError("failed to reload nginx")


def stop_and_remove_container(container_name: str):
    try:
        container = get_containers_by_filter(f"name={container_name}")
    except RuntimeError as e:
        raise e

    if not container:
        LOG.warning("no running container found for '%s'", container_name)
        return

    result = subprocess.run(["docker", "stop", container_name], capture_output=True)
    if result.returncode == 0:
        LOG.info("stopped container '%s'", container_name)
    else:
        raise RuntimeError(f"error stopping old container '{container_name}'")

    result = subprocess.run(["docker", "rm", container_name], capture_output=True)
    if result.returncode == 0:
        LOG.info("removed container '%s'", container_name)
    else:
        raise RuntimeError(f"error removing old container '{container_name}'")


def main(args: Args):
    validate_args(args)

    docker_network_name = f"{args.container_name}_net"
    create_docker_network(docker_network_name)

    # create new app container -------------------------------------------------
    try:
        log_in_to_github_container_registry(args.ghcr_username, args.gh_pat)
    except RuntimeError as e:
        LOG.error(str(e))

    try:
        next_static_volume = new_static_volume_for_next(args.container_name)
    except RuntimeError as e:
        LOG.error(str(e))

    try:
        cur_server_colour, next_server_colour = get_server_colours(args.container_name)
        cur_container_name = f"{args.container_name}_{cur_server_colour.value}"
        next_container_name = f"{args.container_name}_{next_server_colour.value}"
        next_port = PortColour[next_server_colour.upper()]
    except RuntimeError as e:
        LOG.error(str(e))
        sys.exit(1)

    try:
        create_next_app_container(
            docker_image=args.docker_image,
            network_name=docker_network_name,
            next_container_name=next_container_name,
            next_port=next_port,
            next_static_volume=next_static_volume,
            env_file_path=args.env_file_path,
        )
    except RuntimeError as e:
        LOG.error(str(e))
        sys.exit(1)

    run_django_migrations_in_next_container(next_container_name)

    try:
        if service_is_healthy(protocol="http", port=next_port.value):
            LOG.info("next container '%s' is healthy", next_container_name)
        else:
            LOG.error("next container '%s' is not healthy", next_container_name)
            sys.exit(1)
    except RuntimeError as e:
        LOG.error(str(e))
        sys.exit(1)

    # configure certificates and nginx -----------------------------------------
    try:
        create_self_signed_cert(args.ssl_dir)
    except Exception as e:
        LOG.error("failed to create self-signed cert: %s", e)
        sys.exit(1)

    try:
        update_nginx_proxy_target(next_port, args.nginx_conf_dir)
    except Exception as e:
        LOG.error("failed to update nginx: %s", e)
        sys.exit(1)

    # clean up -----------------------------------------------------------------
    try:
        stop_and_remove_container(cur_container_name)
    except RuntimeError as e:
        LOG.error(str(e))
        sys.exit(1)
    finally:
        subprocess.run(
            ["docker", "volume", "prune", "--all", "--force"],
        )

    LOG.info("now serving from '%s:%s'", next_container_name, next_port)
    LOG.info("deployment done.")


if __name__ == "__main__":
    set_up_basic_logging()

    parser = get_argument_parser()
    args_ns = parser.parse_args(args=None if sys.argv[1:] else ["--help"])
    args = Args(
        ghcr_username=args_ns.ghcr_username,
        gh_pat=args_ns.gh_pat,
        docker_image=args_ns.image,
        container_name=args_ns.name,
        env_file_path=args_ns.env_file,
        ssl_dir=args_ns.ssl_dir,
        nginx_conf_dir=args_ns.nginx_conf_dir,
    )

    main(args)
