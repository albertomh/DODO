import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from jinja2 import Template

from digitalocean_deployment_orchestrator.types import EnvVarDataClass


def import_module_from_path(file_path: Path) -> ModuleType:
    module_name = file_path.stem
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import from {file_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def render_cloud_config(template_path: Path, context: EnvVarDataClass) -> str:
    """Generate a cloud config YAML definition by applying a context to a template.

    Args:
      template_path: The path to a cloud config template, a `.yaml.jinja` file.
      context: A dataclass that sources its values from environment variables.

    Returns:
      The plain-text contents of a cloud-config YAML file, ready to be passed to
      the body of a `client.droplets.create()` call (ie. a DropletRequest object).

    Usage:
      ```
      CLOUD_CONFIG_DIR = Path(__file__).parents[1] / "cloud_config_templates"

      DropletRequest(
          user_data=render_cloud_config(
              CLOUD_CONFIG_DIR / "app_server.yaml.jinja",
              AppServerEnv.from_env()
          ),
          ...
      )
      ```
    """
    if not template_path.exists():
        raise FileNotFoundError(template_path)

    template_text = template_path.read_text(encoding="utf-8")
    return Template(template_text).render(**context.as_dict())
