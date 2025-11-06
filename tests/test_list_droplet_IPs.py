from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from digitalocean_deployment_orchestrator.list_droplet_IPs import (
    get_droplet_ips_for_env,
)
from digitalocean_deployment_orchestrator.list_droplet_IPs import (
    main as get_droplet_ips__main,
)
from digitalocean_deployment_orchestrator.types import Environment


@pytest.fixture
def fake_droplets():
    return [
        {
            "id": 1,
            "name": "droplet-1",
            "tags": ["wkid:11111111-1111-1111-1111-111111111111"],
            "networks": {"v4": [{"ip_address": "10.0.0.1"}]},
        },
        {
            "id": 2,
            "name": "droplet-2",
            "tags": ["wkid:22222222-2222-2222-2222-222222222222"],
            "networks": {"v4": [{"ip_address": "10.0.0.2"}]},
        },
    ]


@pytest.fixture
def fake_client(fake_droplets):
    client = MagicMock()
    client.droplets.list.return_value = {"droplets": fake_droplets}
    return client


class TestGetDropletIPsForEnv:
    @patch("digitalocean_deployment_orchestrator.list_droplet_IPs.get_public_ip")
    @patch("digitalocean_deployment_orchestrator.list_droplet_IPs.get_wkid_from_tags")
    def test_get_droplet_ips_for_env_basic(
        self, mock_get_wkid_from_tags, mock_get_public_ip, fake_client
    ):
        mock_get_wkid_from_tags.side_effect = [
            UUID("11111111-1111-1111-1111-111111111111"),
            UUID("22222222-2222-2222-2222-222222222222"),
        ]
        mock_get_public_ip.side_effect = ["10.0.0.1", "10.0.0.2"]

        result = get_droplet_ips_for_env(fake_client, Environment.TEST)

        assert result == {
            UUID("11111111-1111-1111-1111-111111111111"): "10.0.0.1",
            UUID("22222222-2222-2222-2222-222222222222"): "10.0.0.2",
        }
        fake_client.droplets.list.assert_called_once_with(tag_name=Environment.TEST.tag)

    @patch(
        "digitalocean_deployment_orchestrator.list_droplet_IPs.get_public_ip",
        return_value=None,
    )
    @patch(
        "digitalocean_deployment_orchestrator.list_droplet_IPs.get_wkid_from_tags",
        return_value=None,
    )
    def test_get_droplet_ips_skips_invalid(self, mock_wkid, mock_ip, fake_client):
        result = get_droplet_ips_for_env(fake_client, Environment.TEST)
        assert result == {}


class TestMain:
    @patch("builtins.print")
    @patch(
        "digitalocean_deployment_orchestrator.list_droplet_IPs.get_droplet_ips_for_env"
    )
    def test_main_prints(self, mock_get_droplet_ips_for_env, mock_print):
        mock_get_droplet_ips_for_env.return_value = {
            UUID("33333333-3333-3333-3333-333333333333"): "192.168.0.1"
        }

        fake_client = MagicMock()
        get_droplet_ips__main(do_client=fake_client, env=Environment.TEST)

        mock_print.assert_called_once_with("192.168.0.1")
        mock_get_droplet_ips_for_env.assert_called_once_with(
            fake_client, Environment.TEST
        )
