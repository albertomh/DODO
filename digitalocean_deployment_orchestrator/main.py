from importlib.metadata import version

import structlog

from digitalocean_deployment_orchestrator.logging import configure_logging

configure_logging()


def main():
    """Entrypoint for digitalocean_deployment_orchestrator."""
    logger = structlog.get_logger()
    logger.info("digitalocean_deployment_orchestrator", version=f"v{version('digitalocean_deployment_orchestrator')}")
    return


if __name__ == "__main__":  # pragma: no cover
    main()
