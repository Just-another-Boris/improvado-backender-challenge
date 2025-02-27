from importlib import import_module
from typing import Type


def get_class_by_full_path(path: str) -> Type:
    module_path, class_name = path.rsplit('.', 1)
    module = import_module(module_path)
    return getattr(module, class_name)
