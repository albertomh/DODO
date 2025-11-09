from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from digitalocean_deployment_orchestrator.deploy.blue_green_deploy import (
    Args,
    PortColour,
    ServerColour,
    create_docker_network,
    create_next_app_container,
    create_self_signed_cert,
    get_containers_by_filter,
    get_server_colours,
    log_in_to_github_container_registry,
    new_static_volume_for_next,
    run_django_migrations_in_next_container,
    stop_and_remove_container,
    update_nginx_proxy_target,
    validate_args,
)


class TestArgs:
    def test_validate_args_valid(self):
        args = Args(
            "user",
            "github_pat_123",
            "repo/image",
            "name",
            "/tmp/.env",
            Path("/tmp/ssl"),
            Path("/tmp/nginx"),
        )
        validate_args(args)

    @pytest.mark.parametrize(
        "pat", ["badtoken", "gh_", "token"], ids=["no_prefix", "short", "random"]
    )
    def test_validate_args_invalid_pat(self, pat):
        args = Args(
            "u", pat, "repo/img", "c", "/tmp/x", Path("/tmp/ssl"), Path("/tmp/nginx")
        )
        with pytest.raises(ValueError):
            validate_args(args)

    def test_validate_args_invalid_image(self):
        args = Args(
            "user",
            "github_pat_xxx",
            "badimage",
            "c",
            "/tmp/x",
            Path("/tmp/ssl"),
            Path("/tmp/nginx"),
        )
        with pytest.raises(ValueError):
            validate_args(args)


@patch("digitalocean_deployment_orchestrator.deploy.blue_green_deploy.subprocess.run")
def test_create_docker_network_creates_if_missing(mock_run):
    mock_run.side_effect = [
        MagicMock(stdout="default\nbridge\n"),
        MagicMock(),
    ]
    create_docker_network("app_net")
    assert mock_run.call_count == 2


class TestLogInToGithubContainerRegistry:
    @patch("digitalocean_deployment_orchestrator.deploy.blue_green_deploy.subprocess.run")
    def test_log_in_to_ghcr_success(self, mock_run, caplog):
        mock_run.return_value = MagicMock(returncode=0)
        log_in_to_github_container_registry("user", "token")
        mock_run.assert_called_once()
        assert mock_run.return_value.returncode == 0

    @patch("digitalocean_deployment_orchestrator.deploy.blue_green_deploy.subprocess.run")
    def test_log_in_to_ghcr_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        with pytest.raises(RuntimeError):
            log_in_to_github_container_registry("u", "bad")


class TestNewStaticVolumeForNext:
    @patch("digitalocean_deployment_orchestrator.deploy.blue_green_deploy.datetime")
    @patch("digitalocean_deployment_orchestrator.deploy.blue_green_deploy.subprocess.run")
    def test_new_static_volume_success(self, mock_run, mock_dt):
        mock_dt.now.return_value.strftime.return_value = "20250101T000000"
        mock_run.return_value = MagicMock(returncode=0)
        vol = new_static_volume_for_next("myapp")
        assert "myapp_static_20250101T000000" in vol

    @patch("digitalocean_deployment_orchestrator.deploy.blue_green_deploy.subprocess.run")
    def test_new_static_volume_failure(self, mock_run):
        from subprocess import CalledProcessError

        mock_run.side_effect = CalledProcessError(1, "docker")
        with pytest.raises(RuntimeError):
            new_static_volume_for_next("failapp")


@patch("digitalocean_deployment_orchestrator.deploy.blue_green_deploy.subprocess.run")
def test_get_containers_by_filter_parses_output(mock_run):
    mock_run.return_value = MagicMock(
        stdout="id123\tname\t0.0.0.0:8000->8000/tcp\n", returncode=0
    )
    out = get_containers_by_filter("name=app")
    assert out[0]["Names"] == "name"


class TestGetServerColours:
    @patch(
        "digitalocean_deployment_orchestrator.deploy.blue_green_deploy.get_containers_by_filter"
    )
    def test_get_server_colours_blue(self, mock_get):
        mock_get.return_value = [
            {"ID": "1", "Names": "c", "Ports": "0.0.0.0:8000->8000/tcp"}
        ]
        cur, nxt = get_server_colours("app")
        assert (cur, nxt) == (ServerColour.BLUE, ServerColour.GREEN)

    @patch(
        "digitalocean_deployment_orchestrator.deploy.blue_green_deploy.get_containers_by_filter"
    )
    def test_get_server_colours_no_container(self, mock_get):
        mock_get.return_value = []
        cur, nxt = get_server_colours("app")
        assert cur == ServerColour.BLUE
        assert nxt == ServerColour.GREEN


class TestCreateNextAppContainer:
    @patch("digitalocean_deployment_orchestrator.deploy.blue_green_deploy.subprocess.run")
    def test_create_next_app_container_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        create_next_app_container(
            docker_image="repo/img",
            network_name="net",
            next_container_name="c",
            next_port=PortColour.GREEN,
            next_static_volume="v",
            env_file_path="/tmp/.env",
        )
        assert mock_run.call_count >= 2

    @patch("digitalocean_deployment_orchestrator.deploy.blue_green_deploy.subprocess.run")
    def test_create_next_app_container_failure(self, mock_run):
        # First call (pull) succeeds, second (rm) succeeds, third (run) fails
        mock_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=0),
            MagicMock(returncode=1, stderr="error"),
        ]
        with pytest.raises(RuntimeError):
            create_next_app_container(
                docker_image="repo/img",
                network_name="net",
                next_container_name="c",
                next_port=PortColour.GREEN,
                next_static_volume="v",
                env_file_path="/tmp/.env",
            )


@patch("digitalocean_deployment_orchestrator.deploy.blue_green_deploy.subprocess.run")
def test_run_django_migrations_success(mock_run, caplog):
    import logging

    caplog.set_level(logging.INFO)
    mock_run.return_value = MagicMock(returncode=0)
    run_django_migrations_in_next_container("c")
    assert "ran Django migrations" in caplog.text


class TestCreateSelfSignedCert:
    @patch("digitalocean_deployment_orchestrator.deploy.blue_green_deploy.subprocess.run")
    def test_create_self_signed_cert_creates(self, mock_run, tmp_path):
        cert_dir = tmp_path
        create_self_signed_cert(cert_dir)

        assert any("openssl" in str(call) for call in mock_run.call_args_list)

    def test_create_self_signed_cert_existing(self, tmp_path):
        cert_dir = tmp_path
        (cert_dir / "certs").mkdir(parents=True)
        (cert_dir / "private").mkdir(parents=True)
        (cert_dir / "certs" / "selfsigned.crt").touch()
        (cert_dir / "private" / "selfsigned.key").touch()

        with patch(
            "digitalocean_deployment_orchestrator.deploy.blue_green_deploy.subprocess.run"
        ) as mock_run:
            create_self_signed_cert(cert_dir)
            assert not any("openssl" in str(call) for call in mock_run.call_args_list)


@patch("digitalocean_deployment_orchestrator.deploy.blue_green_deploy.subprocess.run")
def test_update_nginx_proxy_target_success(mock_run, tmp_path):
    mock_run.side_effect = [
        MagicMock(returncode=0),  # nginx -t
        MagicMock(returncode=0),  # systemctl reload
    ]

    nginx_conf_dir = tmp_path / "nginx_conf"
    (nginx_conf_dir / "sites-enabled").mkdir(parents=True)
    (nginx_conf_dir / "conf.d").mkdir(parents=True)

    module_dir = tmp_path / "deploy" / "digitalocean_deployment_orchestrator" / "deploy"
    module_dir.mkdir(parents=True)
    fake_file = module_dir / "blue_green_deploy.py"
    fake_file.touch()

    correct_deploy_dir = module_dir.parent
    nginx_template_dir = correct_deploy_dir / "nginx"
    nginx_template_dir.mkdir(parents=True)
    template_file = nginx_template_dir / "app.conf.template"
    template_file.write_text("proxy_pass http://localhost:{{APP_PORT}};")

    with patch(
        "digitalocean_deployment_orchestrator.deploy.blue_green_deploy.__file__",
        str(fake_file),
    ):
        update_nginx_proxy_target(PortColour.GREEN, nginx_conf_dir)

    conf_file = nginx_conf_dir / "conf.d" / "app.conf"
    assert conf_file.exists()
    assert "8080" in conf_file.read_text()


@patch("digitalocean_deployment_orchestrator.deploy.blue_green_deploy.subprocess.run")
@patch(
    "digitalocean_deployment_orchestrator.deploy.blue_green_deploy.get_containers_by_filter"
)
def test_stop_and_remove_container_success(mock_get, mock_run):
    mock_get.return_value = [{"ID": "1", "Names": "n", "Ports": ""}]
    mock_run.return_value = MagicMock(returncode=0)
    stop_and_remove_container("n")
    assert mock_run.call_count == 2
