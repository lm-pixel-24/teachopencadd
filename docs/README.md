# Compiling opencadd's Documentation

The docs for this project are built with [Sphinx](http://www.sphinx-doc.org/en/master/) and [Pandoc](https://pandoc.org/installing.html).
To compile the docs, first ensure that Sphinx and the ReadTheDocs theme are installed.


```bash
pip install -r requirements.txt
```


Once installed, you can use the `Makefile` in this directory to compile static HTML pages by
```bash
make clean
make html
```

The compiled docs will be in the `_build` directory and can be viewed by opening `index.html` (which may itself
be inside a directory called `html/` depending on what version of Sphinx is installed).

Run the following command to run the web server:
```python -m http.server --directory _build/html```

It will open the website in default `http://localhost:8000`.