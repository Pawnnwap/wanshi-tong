import importlib
import pkgutil
from pathlib import Path
from .base import Module, Analyzer, Reporter, Filter


def _discover(package_path: str, base_class):
    """Auto-discover all subclasses of base_class in the package and instantiate them."""
    pkg_dir = Path(package_path)
    if not pkg_dir.exists():
        return []
    package_name = pkg_dir.name
    instances = []
    for _, module_name, _ in pkgutil.iter_modules([str(pkg_dir)]):
        if module_name.startswith("_"):
            continue
        mod = importlib.import_module(f"{package_name}.{module_name}")
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, base_class)
                and attr is not base_class
                and attr.name
            ):
                instances.append(attr())
    return instances


def discover_modules() -> list[Module]:
    return _discover("modules", Module)


def discover_analyzers() -> list[Analyzer]:
    return _discover("analyzers", Analyzer)


def discover_reporters() -> list[Reporter]:
    return _discover("reporters", Reporter)


def discover_filters() -> list[Filter]:
    return _discover("filters", Filter)
