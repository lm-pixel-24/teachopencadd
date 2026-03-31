# -*- coding: utf-8 -*-
import os
import sys
from datetime import datetime
from importlib.metadata import version as get_version

# -- Path setup --------------------------------------------------------------
# With 'uv run', the package is installed in the environment, 
# so we no longer need the sys.path.insert(0, os.path.abspath("..")) hack.

# -- Project information -----------------------------------------------------
project = "TeachOpenCADD"
current_year = datetime.now().year
copyright = (
    f"2018-{current_year}, Volkamer Lab. Project structure based on the "
    "Computational Molecular Science Python Cookiecutter version 1.1"
)
author = "Volkamer Lab"

# Modern version control: pulls directly from pyproject.toml/metadata
try:
    release = get_version("teachopencadd")
    version = ".".join(release.split(".")[:2])
except Exception:
    version = "dev"
    release = "dev"

# -- General configuration ---------------------------------------------------
extensions = [
    "sphinx.ext.autosummary",
    "sphinx.ext.autodoc",
    "sphinx.ext.mathjax",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.extlinks",
    "sphinx.ext.todo",
    "sphinx_material",
    "nbsphinx",
    "nbsphinx_link",
    "IPython.sphinxext.ipython_console_highlighting",
    "sphinx_copybutton",
    "sphinxext.opengraph",
    "sphinx_gallery.load_style",
]

# nbsphinx settings: ensures it doesn't trip over specific notebook formats
nbsphinx_execute = 'never'
nbsphinx_allow_errors = True

autosummary_generate = True
templates_path = ["_templates"]
source_suffix = ".rst"
master_doc = "index"
language = "en"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "**.ipynb_checkpoints"]

# -- Options for HTML output -------------------------------------------------
html_theme = "sphinx_material"
import sphinx_material
html_theme_path = sphinx_material.html_theme_path()
html_context = sphinx_material.get_html_context()

html_static_path = ["_static", "../talktorials/images"] # Harvesting the PDFs
html_css_files = ["custom.css"]

html_theme_options = {
    "repo_url": "https://github.com/volkamerlab/teachopencadd/",
    "repo_name": "TeachOpenCADD",
    "google_analytics_account": "G-Q6ZE82CNZB",
    "logo_icon": "school",
    "repo_type": "github",
    "globaltoc_depth": 2,
    "color_primary": "teal",
    "color_accent": "cyan",
    "theme_color": "#2196f3",
    "nav_links": [
        {"href": "talktorials", "internal": True, "title": "Our talktorials"},
        {"href": "installing", "internal": True, "title": "Run locally"},
        {"href": "contribute", "internal": True, "title": "Development"},
        {"href": "contact", "internal": True, "title": "Contact"},
        {"href": "citation", "internal": True, "title": "Citation"},
    ],
}

# -- Final Clean-ups --
# This replaces the need for the 'sed' and manual 'cp' commands in CI.
# By adding talktorials/images to html_static_path, Sphinx moves them to _static/
# To reference them in a notebook iframe, use: src="../_static/butina_full.pdf"
