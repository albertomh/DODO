import json
from unittest.mock import MagicMock, patch

import pytest

from digitalocean_deployment_orchestrator.check_service_health import (
    main,
    service_is_healthy,
)


class TestServiceIsHealthy:
    @pytest.mark.parametrize(
        "status,body,expected",
        [
            (200, b'{"healthy": true}', True),
            (200, b'{"healthy": false}', False),
        ],
    )
    def test_service_is_healthy_success(self, status, body, expected):
        mock_res = MagicMock(status=status)
        mock_res.read.return_value = body
        with patch("urllib.request.urlopen", return_value=mock_res):
            result = service_is_healthy(ip="1.2.3.4")
        assert result == expected

    def test_service_is_healthy_non_200_returns_false(self):
        mock_res = MagicMock(status=500)
        with patch("urllib.request.urlopen", return_value=mock_res):
            assert service_is_healthy(ip="1.2.3.4") is False

    def test_service_is_healthy_retries_and_fails(self):
        with (
            patch("urllib.request.urlopen", side_effect=ConnectionRefusedError),
            patch("time.sleep") as mock_sleep,
        ):
            with pytest.raises(ConnectionRefusedError):
                service_is_healthy(ip="1.2.3.4", max_attempts=3)
        mock_sleep.assert_any_call(1.0)
        mock_sleep.assert_any_call(2.0)

    def test_service_is_healthy_invalid_json_raises(self):
        mock_res = MagicMock(status=200)
        mock_res.read.return_value = b"not json"
        with patch("urllib.request.urlopen", return_value=mock_res):
            with pytest.raises(json.JSONDecodeError):
                service_is_healthy(ip="1.2.3.4")

    def test_service_is_healthy_constructs_correct_url(self):
        called_urls = []

        def fake_urlopen(url, context):
            called_urls.append(url)
            mock_res = MagicMock(status=200)
            mock_res.read.return_value = b'{"healthy": true}'
            return mock_res

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            service_is_healthy(protocol="http", ip="10.0.0.1", port="8080")
        assert called_urls[0].startswith("http://10.0.0.1:8080/-/health/")


class TestMain:
    @patch("digitalocean_deployment_orchestrator.check_service_health.service_is_healthy")
    @patch(
        "digitalocean_deployment_orchestrator.check_service_health.get_droplet_ips_for_env"
    )
    def test_main_all_healthy(self, mock_get_ips, mock_is_healthy, caplog):
        mock_get_ips.return_value = {"uuid1": "1.2.3.4", "uuid2": "5.6.7.8"}
        mock_is_healthy.return_value = True

        fake_client = MagicMock()
        fake_env = MagicMock()

        with caplog.at_level("INFO"):
            main(do_client=fake_client, env=fake_env)

        messages = [r.message for r in caplog.records]
        assert any("healthy" in msg for msg in messages)
        mock_is_healthy.assert_called()

    @patch("sys.exit")
    @patch("digitalocean_deployment_orchestrator.check_service_health.service_is_healthy")
    @patch(
        "digitalocean_deployment_orchestrator.check_service_health.get_droplet_ips_for_env"
    )
    def test_main_some_unhealthy(self, mock_get_ips, mock_is_healthy, mock_exit, caplog):
        mock_get_ips.return_value = {"uuid1": "1.2.3.4", "uuid2": "5.6.7.8"}
        mock_is_healthy.side_effect = [True, False]

        main(do_client=MagicMock(), env=MagicMock())
        # one unhealthy triggers sys.exit(1)
        mock_exit.assert_called_once_with(1)
        assert any("unhealthy" in r.message for r in caplog.records)
