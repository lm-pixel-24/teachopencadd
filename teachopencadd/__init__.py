"""
TeachOpenCADD is a collection of Jupyter Notebooks
to help you learn or teach computer aided drug design concepts.

The notebooks themselves are located under ``talktorials/``.
"""

from .config import Settings, settings
from .exceptions import TeachOpenCADDError

__all__ = ["Settings", "settings", "TeachOpenCADDError"]
