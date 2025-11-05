import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import jinja2
import pytest

from digitalocean_deployment_orchestrator.infra import utils


class TestImportModuleFromPath:
    def test_import_module_from_path_success(self, tmp_path):
        mod_path = tmp_path / "dummy_mod.py"
        mod_path.write_text("VALUE = 123")

        module = utils.import_module_from_path(mod_path)

        assert isinstance(module, ModuleType)
        assert module.VALUE == 123
        assert "dummy_mod" in sys.modules

    def test_import_module_from_path_raises_if_spec_none(self, monkeypatch, tmp_path):
        fake_path = tmp_path / "x.py"

        monkeypatch.setattr("importlib.util.spec_from_file_location", lambda *_: None)

        with pytest.raises(ImportError, match="Cannot import"):
            utils.import_module_from_path(fake_path)

    def test_import_module_from_path_raises_if_loader_none(self, monkeypatch, tmp_path):
        fake_path = tmp_path / "y.py"

        class DummySpec:
            loader = None

        monkeypatch.setattr(
            "importlib.util.spec_from_file_location", lambda *_: DummySpec()
        )

        with pytest.raises(ImportError, match="Cannot import"):
            utils.import_module_from_path(fake_path)


@pytest.fixture
def fake_env():
    class FakeEnv:
        def as_dict(self):
            return {"name": "web", "port": 80}

    return FakeEnv()


class TestRenderCloudConfig:
    def test_render_cloud_config_renders_template(self, tmp_path, fake_env):
        tpl = tmp_path / "conf.yaml.jinja"
        tpl.write_text("service: {{ name }}\nport: {{ port }}")

        result = utils.render_cloud_config(tpl, fake_env)

        assert "service: web" in result
        assert "port: 80" in result

    def test_render_cloud_config_missing_file(self, tmp_path, fake_env):
        missing = tmp_path / "nope.yaml.jinja"
        with pytest.raises(FileNotFoundError):
            utils.render_cloud_config(missing, fake_env)

    def test_render_cloud_config_empty_context(self, tmp_path):
        tpl = tmp_path / "empty.yaml.jinja"
        tpl.write_text("{{ greeting | default('hello') }}")

        ctx = MagicMock()
        ctx.as_dict.return_value = {}

        result = utils.render_cloud_config(tpl, ctx)
        assert "hello" in result

    def test_render_cloud_config_propagates_jinja_error(self, tmp_path, fake_env):
        tpl = tmp_path / "bad.yaml.jinja"
        tpl.write_text("{{ broken_syntax }}")

        with patch("jinja2.Template.render", side_effect=jinja2.TemplateError("broken")):
            with pytest.raises(jinja2.TemplateError):
                utils.render_cloud_config(tpl, fake_env)
