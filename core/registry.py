import importlib
import pkgutil

from .base import Module, Analyzer, Reporter, Filter


def _discover(package_name: str, base_class):
    """Auto-discover all subclasses of base_class in the package and instantiate them."""
    package = importlib.import_module(package_name)
    instances = []
    for _, module_name, _ in pkgutil.iter_modules(package.__path__):
        if module_name.startswith("_"):
            continue
        mod = importlib.import_module(f"{package_name}.{module_name}")
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, base_class)
                and attr is not base_class
                and attr.__module__ == mod.__name__
                and attr.name
            ):
                instances.append(attr())
    return sorted(instances, key=lambda instance: instance.name)


def discover_modules() -> list[Module]:
    return _discover("modules", Module)


def discover_analyzers() -> list[Analyzer]:
    return _discover("analyzers", Analyzer)


def discover_reporters() -> list[Reporter]:
    return _discover("reporters", Reporter)


def discover_filters() -> list[Filter]:
    return _discover("filters", Filter)
