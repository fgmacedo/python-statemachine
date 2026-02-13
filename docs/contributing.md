# Contributing

* <a class="github-button" href="https://github.com/fgmacedo/python-statemachine" data-icon="octicon-star" aria-label="Star fgmacedo/python-statemachine on GitHub">Star this project</a>
* <a class="github-button" href="https://github.com/fgmacedo/python-statemachine/issues" data-icon="octicon-issue-opened" aria-label="Issue fgmacedo/python-statemachine on GitHub">Open an Issue</a>
* <a class="github-button" href="https://github.com/fgmacedo/python-statemachine/fork" data-icon="octicon-repo-forked" aria-label="Fork fgmacedo/python-statemachine on GitHub">Fork</a>

Contributions are welcome, and they are greatly appreciated! Every little bit helps, and credit
will always be given.

You can contribute in many ways:

## Types of Contributions

### Report Bugs

Report bugs at [https://github.com/fgmacedo/python-statemachine/issues](https://github.com/fgmacedo/python-statemachine/issues).

If you are reporting a bug, please include:

* Your operating system name and version.
* Any details about your local setup that might be helpful in troubleshooting.
* Detailed steps to reproduce the bug.

### Fix Bugs

Look through the GitHub issues for bugs. Anything tagged with "bug"
and "help wanted" is open to whoever wants to implement it.

### Implement Features

Look through the GitHub issues for features. Anything tagged with "enhancement"
and "help wanted" is open to whoever wants to implement it.

### Write Documentation

Python State Machine could always use more documentation, whether as part of the
official Python State Machine docs, in docstrings, or even on the web in blog posts,
articles, and such.

### Add a translation


Extract a `Portable Object Template` (`POT`) file:

```shell
pybabel extract statemachine -o statemachine/locale/statemachine.pot
```

Then, copy the template as a `.po` file into the target locale folder. For example, if you're adding support for Brazilian Portuguese language, the code is `pt_BR`, and the file path should be `statemachine/locale/pt_BR/LC_MESSAGES/statemachine.po`:

```shell
cp statemachine/locale/statemachine.pot statemachine/locale/pt_BR/LC_MESSAGES/statemachine.po
```

Then open the `statemachine.po` and translate.

After translation, to get the new language working locally, you need to compile the `.po` files into `.mo`  (binary format). Run:

```shell
pybabel compile -d statemachine/locale/ -D statemachine
```


On Linux (Debian based), you can test changing the `LANGUAGE` environment variable.

```shell
# If the last line is `Can't guess when in Won.` something went wrong.
LANGUAGE=pt_BR python tests/examples/guess_the_number_machine.py
```

Then open a [pull request](https://github.com/fgmacedo/python-statemachine/pulls) with your translation file.

### Submit Feedback

The best way to send feedback is to file an issue at https://github.com/fgmacedo/python-statemachine/issues.

If you are proposing a feature:

* Explain in detail how it would work.
* Keep the scope as narrow as possible, to make it easier to implement.
* Remember that this is a volunteer-driven project, and that contributions
  are welcome :)

## Get Started!

Ready to contribute? Here's how to set up `python-statemachine` for local development.

1. Install dependencies.
   1. [graphviz](https://graphviz.org/download/#linux)
   1. [uv](https://docs.astral.sh/uv/getting-started/installation/)

1. Fork the `python-statemachine` repository on GitHub.

1. Clone the forked repository to your local machine by running::

        git clone https://github.com/YOUR-USERNAME/python-statemachine.git.


1. Run `uv sync` once to install all the development dependencies and create a virtual environment::

        uv sync --all-extras

2. Install the pre-commit validations:

        pre-commit install

3. Create a branch for local development:

        git checkout -b <name-of-your-bugfix-or-feature>

4. Make changes to the code.

5. Run tests to ensure they pass by running:

        uv run pytest

6. Update the documentation as needed.

    Build the documentation:

        uv run sphinx-build docs docs/_build/html


    Now you can serve the local documentation using a webserver, like the built-in included
    with python:

        python -m http.server --directory docs/_build/html

    And access your browser at http://localhost:8000/

    If you're specially writting documentation, I strongly recommend using `sphinx-autobuild`
    as it improves the workflow watching for file changes and with live reloading:

        uv run sphinx-autobuild docs docs/_build/html --re-ignore "auto_examples/.*"

    Sometimes you need a full fresh of the files being build for docs, you can safely remove
    all automatically generated files to get a clean state by running:

        rm -rf docs/_build/ docs/auto_examples

1. Commit your changes and push them to your forked repository:

        git add -A .
        git commit -s -m "Your detailed description of your changes."
        git push origin name-of-your-bugfix-or-feature

1. Create a pull request on the original repository for your changes to be reviewed and potentially
merged. Be sure to follow the project's code of conduct and contributing guidelines.

1. Use `exit` to leave the virtual environment.

## Pull Request Guidelines

Before you submit a pull request, check that it meets these guidelines:

1. The pull request should include tests.
2. If the pull request adds functionality, the docs should be updated. Put
   your new functionality into a function with a docstring, and add the
   feature to the list in the next release notes.
3. Consider adding yourself to the contributor's list.
4. The pull request should work for all supported Python versions.

## Releasing a New Version

This project uses [git-flow](https://github.com/nvie/gitflow) for release management and
publishes to PyPI automatically via GitHub Actions when a version tag is pushed.

### Prerequisites

- You must be on the `develop` branch with a clean working tree.
- `git-flow` must be installed and initialized:

  ```shell
  brew install git-flow   # macOS
  git flow init           # use main for production, develop for next release
  ```

- All changes intended for the release must already be merged into `develop`.

### Step-by-step release process

The following steps use version `X.Y.Z` as a placeholder. Replace it with the actual version
number (e.g., `2.6.0`).

#### 1. Start the release branch

```shell
git checkout develop
git pull origin develop
git flow release start X.Y.Z
```

This creates and switches to a `release/X.Y.Z` branch based on `develop`.

#### 2. Bump the version number

Update the version string in **both** files:

- `pyproject.toml` — the `version` field under `[project]`
- `statemachine/__init__.py` — the `__version__` variable

#### 3. Update translations

Extract new translatable strings, merge them into all existing `.po` files, translate the
new entries, and compile:

```shell
uv run pybabel extract statemachine -o statemachine/locale/statemachine.pot
uv run pybabel update -i statemachine/locale/statemachine.pot -d statemachine/locale/ -D statemachine
# Edit each .po file to translate new empty msgstr entries
uv run pybabel compile -d statemachine/locale/ -D statemachine
```

```{note}
The `.pot` and `.mo` files are git-ignored. Only the `.po` source files are committed.
The compiled `.mo` files may cause test failures if your system locale matches a translated
language (error messages will appear translated instead of in English). Delete them after
verifying translations work: `rm -f statemachine/locale/*/LC_MESSAGES/statemachine.mo`
```

#### 4. Write release notes

Create `docs/releases/X.Y.Z.md` documenting all changes since the previous release. Include
sections for new features, bugfixes, performance improvements, and miscellaneous changes.
Reference GitHub issues/PRs where applicable.

Add the new file to the toctree in `docs/releases/index.md` (at the top of the appropriate
major version section).

Update any related documentation pages (e.g., if a bugfix adds a new behavior that users
should know about).

#### 5. Run linters and tests

```shell
uv run ruff check .
uv run ruff format --check .
uv run mypy statemachine/
uv run pytest -n auto
```

All checks must pass before committing.

#### 6. Commit

Stage all changed files and commit. The pre-commit hooks will run ruff, mypy, and pytest
automatically.

```shell
git add <files>
git commit -m "chore: prepare release X.Y.Z"
```

#### 7. Finish the release

```shell
git flow release finish X.Y.Z -m "vX.Y.Z"
```

This will:
- Merge `release/X.Y.Z` into `main`
- Create an annotated tag `X.Y.Z` on `main`
- Merge `main` back into `develop`
- Delete the `release/X.Y.Z` branch

```{note}
If tagging fails (e.g., GPG or editor issues), create the tag manually and re-run:
`git tag -a X.Y.Z -m "vX.Y.Z"` then `git flow release finish X.Y.Z -m "vX.Y.Z"`.
```

#### 8. Update the `latest` tag and push

```shell
git tag latest -f
git push origin main develop --tags -f
```

Force-pushing tags is needed to move the `latest` tag.

#### 9. Verify the release

The tag push triggers the `release` GitHub Actions workflow (`.github/workflows/release.yml`),
which will:

1. Check out the tag
2. Run the full test suite
3. Build the sdist and wheel with `uv build`
4. Publish to PyPI using trusted publishing

Monitor the workflow run at `https://github.com/fgmacedo/python-statemachine/actions` to
confirm the release was published successfully.
