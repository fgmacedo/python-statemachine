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

Ready to contribute? Here's how to set up `python-statemachine` for local development.

1. Fork the `python-statemachine` repo on GitHub.
2. Clone your fork locally::

    $ git clone git@github.com:your_name_here/python-statemachine.git

3. Install your local copy into a virtualenv. Assuming you have virtualenvwrapper installed, this is how you set up your fork for local development::

    $ mkvirtualenv python-statemachine
    $ cd python-statemachine/
    $ python setup.py develop

4. Create a branch for local development::

    $ git checkout -b name-of-your-bugfix-or-feature

   Now you can make your changes locally.

5. When you're done making changes, check that your changes pass flake8 and the tests, including
   testing other Python versions with tox::

    $ flake8 statemachine tests
    $ py.test
    $ tox

   To get flake8 and tox, just pip install them into your virtualenv.

6. To build the documentation locally, run::

    $ sphinx-build docs docs/_build/html

   Now you can serve the local documentation using a webserver, like the built-in included
   with python::

    $ python -m http.server --directory docs/_build/html

   And access your browser at http://localhost:8000/

   If you're specially writting documentation, I strongly recommend using ``sphinx-autobuild``
   as it improves the workflow watching for file changes and with live reloading::

    $ sphinx-autobuild docs docs/_build/html --re-ignore "auto_examples/.*"

   Sometimes you need a full fresh of the files being build for docs, you can use::

    $ rm -rf docs/_build/ docs/auto_examples

.. note::

    In order to get the tox working for all versions, I usually run pyenv enabling shell for
    those versions::

    $ pyenv shell 3.8.1/envs/python-statemachine 3.7.6 3.6.10 3.5.9 2.7.17

1. Commit your changes and push your branch to GitHub::

    $ git add .
    $ git commit -m "Your detailed description of your changes."
    $ git push origin name-of-your-bugfix-or-feature

2. Submit a pull request through the GitHub website.

Pull Request Guidelines
-----------------------

Before you submit a pull request, check that it meets these guidelines:

1. The pull request should include tests.
2. If the pull request adds functionality, the docs should be updated. Put
   your new functionality into a function with a docstring, and add the
   feature to the list in README.rst.
3. The pull request should work for Python 2.7, 3.3, 3.4 and 3.5. Check
   https://travis-ci.org/fgmacedo/python-statemachine/pull_requests
   and make sure that the tests pass for all supported Python versions.

Tips
----

To run a subset of tests::

$ py.test tests.test_statemachine

