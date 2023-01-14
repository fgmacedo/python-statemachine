.. highlight:: shell

============
Contributing
============

Contributions are welcome, and they are greatly appreciated! Every
little bit helps, and credit will always be given.

You can contribute in many ways:

Types of Contributions
----------------------

Report Bugs
~~~~~~~~~~~

Report bugs at https://github.com/fgmacedo/python-statemachine/issues.

If you are reporting a bug, please include:

* Your operating system name and version.
* Any details about your local setup that might be helpful in troubleshooting.
* Detailed steps to reproduce the bug.

Fix Bugs
~~~~~~~~

Look through the GitHub issues for bugs. Anything tagged with "bug"
and "help wanted" is open to whoever wants to implement it.

Implement Features
~~~~~~~~~~~~~~~~~~

Look through the GitHub issues for features. Anything tagged with "enhancement"
and "help wanted" is open to whoever wants to implement it.

Write Documentation
~~~~~~~~~~~~~~~~~~~

Python State Machine could always use more documentation, whether as part of the
official Python State Machine docs, in docstrings, or even on the web in blog posts,
articles, and such.

Submit Feedback
~~~~~~~~~~~~~~~

The best way to send feedback is to file an issue at https://github.com/fgmacedo/python-statemachine/issues.

If you are proposing a feature:

* Explain in detail how it would work.
* Keep the scope as narrow as possible, to make it easier to implement.
* Remember that this is a volunteer-driven project, and that contributions
  are welcome :)

Get Started!
------------

Ready to contribute? Here's how to set up ``python-statemachine`` for local development.


1. Fork the ``python-statemachine`` repository on GitHub.

2. Clone the forked repository to your local machine by running::

    git clone https://github.com/YOUR-USERNAME/python-statemachine.git.


3. Run ``poetry install`` to install all the dependencies and create a virtual environment::

    poetry install

4. Install the pre-commit validations::

    pre-commit install

5. Create a branch for local development::

    git checkout -b name-of-your-bugfix-or-feature

6. Make changes to the code.
7. Run tests to ensure they pass by running::

    poetry run pytest

8. Update the documentation as needed.

    Build the documentation::

        poetry run sphinx-build docs docs/_build/html


    Now you can serve the local documentation using a webserver, like the built-in included
    with python::

        python -m http.server --directory docs/_build/html

    And access your browser at http://localhost:8000/

    If you're specially writting documentation, I strongly recommend using ``sphinx-autobuild``
    as it improves the workflow watching for file changes and with live reloading::

        poetry run sphinx-autobuild docs docs/_build/html --re-ignore "auto_examples/.*"

    Sometimes you need a full fresh of the files being build for docs, you can safelly remove
    all automatically generated files to get a clean state by running::

        rm -rf docs/_build/ docs/auto_examples

9. Commit your changes and push them to your forked repository::

    git add -A .
    git commit -m "Your detailed description of your changes."
    git push origin name-of-your-bugfix-or-feature

10. Create a pull request on the original repository for your changes to be reviewed and potentially
merged. Be sure to follow the project's code of conduct and contributing guidelines.


.. note::

    In order to get the tox working for all versions, I usually use pyenv enabling shell for
    those versions.


Pull Request Guidelines
-----------------------

Before you submit a pull request, check that it meets these guidelines:

1. The pull request should include tests.
2. If the pull request adds functionality, the docs should be updated. Put
   your new functionality into a function with a docstring, and add the
   feature to the list in the next release notes.
3. Consider adding yourself on the contributors list.
4. The pull request should work for all supported Python versions.
