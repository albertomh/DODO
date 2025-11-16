import json
import types
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from digitalocean_deployment_orchestrator.infra import apply


@pytest.fixture
def fake_blueprint(tmp_path):
    bp = {
        "environment": MagicMock(value="prod"),
        "droplets": [
            {
                "name": "web",
                "well_known_uuid": UUID("12345678-1234-5678-1234-567812345678"),
                "tags": [],
            }
        ],
    }
    module_path = tmp_path / "bp1.py"
    module_path.write_text("BLUEPRINT = {}")  # overwritten later in test
    return bp, module_path


class TestLoadEnvironmentBlueprint:
    @patch("digitalocean_deployment_orchestrator.infra.apply.import_module_from_path")
    def test_load_environment_blueprint_single_ok(
        self, mock_import, tmp_path, fake_blueprint
    ):
        bp, module_path = fake_blueprint
        mock_mod = types.SimpleNamespace(BLUEPRINT=bp)
        mock_import.return_value = mock_mod
        module_path.write_text("BLUEPRINT = {}")

        result = apply.load_environment_blueprint(tmp_path, bp["environment"])

        droplet = result["droplets"][0]
        assert any(tag.startswith("env:") for tag in droplet["tags"])
        assert any(tag.startswith("wkid:") for tag in droplet["tags"])
        mock_import.assert_called_once_with(module_path)

    @patch("digitalocean_deployment_orchestrator.infra.apply.import_module_from_path")
    def test_load_environment_blueprint_multiple_raises(
        self, mock_import, tmp_path, fake_blueprint
    ):
        bp, module_path = fake_blueprint
        mod = types.SimpleNamespace(BLUEPRINT=bp)
        mock_import.return_value = mod
        (tmp_path / "bp2.py").write_text("BLUEPRINT = {}")

        # simulate two blueprints for same env
        mock_import.side_effect = [mod, mod]

        with pytest.raises(ValueError):
            apply.load_environment_blueprint(tmp_path, bp["environment"])

    @patch("digitalocean_deployment_orchestrator.infra.apply.import_module_from_path")
    def test_load_environment_blueprint_none_found(self, mock_import, tmp_path):
        mock_import.return_value = types.SimpleNamespace()
        (tmp_path / "bp1.py").write_text("BLUEPRINT = None")

        with pytest.raises(RuntimeError):
            apply.load_environment_blueprint(tmp_path, MagicMock(value="staging"))


@pytest.fixture
def fake_env():
    env = MagicMock()
    env.value = "prod"
    env.tag = "env:prod"
    return env


@pytest.fixture
def fake_do_client():
    client = MagicMock()

    client.droplets.list.return_value = {"droplets": []}
    client.droplets.create.return_value = {"droplet": {"id": 1}}

    return client


class TestManageDroplets:
    @patch("digitalocean_deployment_orchestrator.infra.apply.get_wkid_from_tags")
    def test_manage_droplets_no_changes(self, mock_get_wkid, fake_do_client, fake_env):
        mock_get_wkid.side_effect = [UUID("a" * 32)] * 2
        fake_do_client.droplets.list.return_value = {
            "droplets": [{"tags": ["wkid:a" * 32], "name": "existing"}]
        }

        bp_droplet = {
            "tags": ["wkid:a" * 32],
            "well_known_uuid": UUID("a" * 32),
            "name": "existing",
        }
        apply.manage_droplets(True, fake_do_client, fake_env, [bp_droplet])

        fake_do_client.droplets.create.assert_not_called()
        fake_do_client.droplets.destroy.assert_not_called()

    @patch("digitalocean_deployment_orchestrator.infra.apply.get_wkid_from_tags")
    def test_manage_droplets_dry_run_creates(
        self, mock_get_wkid, fake_do_client, fake_env, capsys
    ):
        mock_get_wkid.side_effect = [None, UUID("1" * 32), UUID("1" * 32)]
        bp_droplet = {
            "name": "web",
            "tags": ["wkid:11111111-1111-1111-1111-111111111111"],
            "well_known_uuid": UUID("1" * 32),
            "user_data": "secret",
        }

        apply.manage_droplets(True, fake_do_client, fake_env, [bp_droplet])

        logs = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
        events = {entry["event"]: entry for entry in logs}
        assert "Droplets to create" in events
        assert events["Droplet comparison"]["to_create"] == 1
        fake_do_client.droplets.create.assert_not_called()

    @patch("digitalocean_deployment_orchestrator.infra.apply.get_wkid_from_tags")
    def test_manage_droplets_creates(self, mock_get_wkid):
        fake_do_client = MagicMock()
        fake_env = MagicMock()
        fake_env.tag = "env:test"
        fake_env.value = "test"

        fake_do_client.droplets.list.return_value = {"droplets": []}
        fake_do_client.droplets.create.return_value = {"droplet": {"id": 999}}

        mock_get_wkid.return_value = UUID("1" * 32)

        bp_droplet = {
            "name": "web",
            "tags": ["wkid:11111111-1111-1111-1111-111111111111"],
            "well_known_uuid": UUID("1" * 32),
            "user_data": "secret",
        }

        apply.manage_droplets(False, fake_do_client, fake_env, [bp_droplet])

        fake_do_client.droplets.create.assert_called_once()
        call_args = fake_do_client.droplets.create.call_args[1]
        assert "body" in call_args
        assert call_args["body"]["name"] == "web"

    @patch("digitalocean_deployment_orchestrator.infra.apply.get_wkid_from_tags")
    def test_manage_droplets_destroy_dry_run(
        self, mock_get_wkid, fake_do_client, fake_env, capsys
    ):
        mock_get_wkid.side_effect = [UUID("1" * 32), None, UUID("1" * 32)]
        fake_do_client.droplets.list.return_value = {
            "droplets": [
                {
                    "id": 321,
                    "tags": ["wkid:11111111-1111-1111-1111-111111111111"],
                    "name": "old",
                }
            ]
        }

        apply.manage_droplets(True, fake_do_client, fake_env, [])

        logs = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
        events = {entry["event"]: entry for entry in logs}
        assert "Droplets to destroy" in events
        assert events["Droplet comparison"]["to_destroy"] == 1
        fake_do_client.droplets.create.assert_not_called()

    @patch("digitalocean_deployment_orchestrator.infra.apply.get_wkid_from_tags")
    def test_manage_droplets_destroy(self, mock_get_wkid, fake_do_client, fake_env):
        mock_get_wkid.return_value = UUID("1" * 32)

        fake_do_client.droplets.list.return_value = {
            "droplets": [
                {
                    "id": 123,
                    "tags": ["wkid:11111111-1111-1111-1111-111111111111"],
                    "name": "old",
                }
            ]
        }

        apply.manage_droplets(False, fake_do_client, fake_env, [])

        fake_do_client.droplets.destroy.assert_called_once_with(droplet_id=123)


class TestApply:
    @patch("digitalocean_deployment_orchestrator.infra.apply.load_environment_blueprint")
    @patch("digitalocean_deployment_orchestrator.infra.apply.manage_droplets")
    def test_apply_calls_correctly(
        self, mock_manage_droplets, mock_load, fake_do_client, fake_env
    ):
        bp = {"droplets": [{"name": "web"}]}
        mock_load.return_value = bp

        apply.apply(False, fake_do_client, Path("."), fake_env)
        mock_manage_droplets.assert_called_once_with(
            False, fake_do_client, fake_env, bp["droplets"]
        )
