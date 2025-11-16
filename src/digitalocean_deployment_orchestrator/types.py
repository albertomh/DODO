import os
from dataclasses import dataclass, fields
from enum import StrEnum, auto

# --- Generic base classes ---------------------------------------------------------------


@dataclass(frozen=True)
class EnvVarDataClass:
    """Base class for dataclasses that source their values from environment variables.

    Subclasses must define fields that map to environment variables eg.
    ```
    @dataclass(frozen=True)
    class PostgresServerEnv(EnvVarDataClass):
        ssh__public_key: str
    ```
    code that uses an object created from the above class will expect the environment
    variable `SSH__PUBLIC_KEY` to be set.

    Initialise with values from the environment by calling the `from_env()` class method.
    """

    @classmethod
    def from_env(cls):
        """Load and validate all required environment variables.

        Raises:
          EnvironmentError if any are missing.
        """
        missing = []
        values = {}

        for f in fields(cls):
            env_name = f.name.upper()
            val = os.getenv(env_name)
            if not val:
                missing.append(env_name)
            else:
                values[f.name] = val

        if missing:
            raise OSError(
                f"Missing environment variables for {cls.__name__}: {', '.join(missing)}"
            )

        return cls(**values)

    def as_dict(self) -> dict[str, str]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


# --- Application types ------------------------------------------------------------------


class Environment(StrEnum):
    TEST = auto()
    LIVE = auto()

    @property
    def tag(self):
        return f"env:{self.value}"
