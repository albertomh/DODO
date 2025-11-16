import json
import logging
from datetime import datetime
from uuid import UUID

import structlog

from digitalocean_deployment_orchestrator.types_DO import DropletResponse, IPVersion


def get_wkid_from_tags(tags: list[str]) -> UUID | None:
    """Get well-known UUID from tags.

    Well-known UUIDs are defined at the top of every Blueprint file.
    """
    uuid_tags = [t for t in tags if t.startswith("wkid")]
    if not uuid_tags:
        return None
    return UUID(uuid_tags[0].split(":")[1])


def get_public_ip(
    droplet: DropletResponse, version: IPVersion | None = None
) -> str | None:
    if version is None:
        version = "v4"
    for net in droplet["networks"][version] + droplet["networks"]["v6"]:
        if net["type"] == "public":
            return net["ip_address"]
    return None


def set_up_basic_logging():
    class PaddedFormatter(logging.Formatter):
        def format(self, record):
            record.levelname = record.levelname.ljust(len("WARNING"))
            record.asctime = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
            return f"{record.levelname} [{record.asctime}] {record.getMessage()}"

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for h in logging.getLogger().handlers:
        h.setFormatter(PaddedFormatter())


def configure_structlog():
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(
                serializer=lambda obj, **kwargs: json.dumps(obj, ensure_ascii=False)
            ),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )
