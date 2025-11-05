from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from digitalocean_deployment_orchestrator import utils


class TestGetDOToken:
    def test_get_do_token_found(self, monkeypatch):
        monkeypatch.delenv("DIGITALOCEAN__TOKEN", raising=False)
        monkeypatch.setenv("DIGITALOCEAN__TOKEN", "secret123")
        assert utils.get_DO_token() == "secret123"

    def test_get_do_token_missing(self, monkeypatch):
        monkeypatch.delenv("DIGITALOCEAN__TOKEN", raising=False)
        with pytest.raises(ValueError, match="DIGITALOCEAN__TOKEN"):
            utils.get_DO_token()


class TestGetDOClient:
    @patch("digitalocean_deployment_orchestrator.utils.Client")
    @patch("digitalocean_deployment_orchestrator.utils.get_DO_token", return_value="tok")
    def test_get_do_client(self, mock_token, mock_client):
        client_instance = MagicMock()
        mock_client.return_value = client_instance
        result = utils.get_DO_client()
        mock_client.assert_called_once_with("tok")
        assert result == mock_client.return_value


class TestGetWKIDFromTags:
    def test_get_wkid_from_tags_valid(self):
        wkid = UUID("12345678-1234-5678-1234-567812345678")
        tags = ["foo", f"wkid:{wkid}", "bar"]
        assert utils.get_wkid_from_tags(tags) == wkid

    def test_get_wkid_from_tags_none(self):
        assert utils.get_wkid_from_tags(["foo", "bar"]) is None


class TestGetPublicIP:
    def test_get_public_ip_default_v4(self, droplet_response):
        assert utils.get_public_ip(droplet_response) == "1.2.3.4"

    def test_get_public_ip_v6_public(self):
        droplet = {
            "networks": {
                "v4": [{"type": "private", "ip_address": "10.0.0.1"}],
                "v6": [{"type": "public", "ip_address": "2001:db8::1"}],
            }
        }
        assert utils.get_public_ip(droplet, version="v6") == "2001:db8::1"

    def test_get_public_ip_none_found(self):
        droplet = {
            "networks": {
                "v4": [{"type": "private", "ip_address": "10.0.0.1"}],
                "v6": [{"type": "private", "ip_address": "fd00::1"}],
            }
        }
        assert utils.get_public_ip(droplet) is None
