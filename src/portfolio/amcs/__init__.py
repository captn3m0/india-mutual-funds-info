import importlib
import pkgutil


def registry() -> dict:
    """slug -> module, for every AMC module in this package."""
    mods = {}
    for info in pkgutil.iter_modules(__path__):
        mod = importlib.import_module(f"{__name__}.{info.name}")
        if hasattr(mod, "list_disclosures"):
            mods[mod.SLUG] = mod
    return dict(sorted(mods.items()))
