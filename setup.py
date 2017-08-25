#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function
import os

from setuptools import setup
import restructuredtext_lint

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

long_description = readme + '\n\n' + history

errors = restructuredtext_lint.lint(long_description)
if errors:
    lines = long_description.splitlines()
    msg = "Long description has errors.\r\n"
    for idx, error in enumerate(errors, 1):
        line = lines[error.line - 1]
        msg += "{}) Linha {}. '{}'\r\n{}\r\n\r\n".format(
            idx, error.line, line, error.full_message)

    print(msg)
    os._exit(1)

requirements = [
    # TODO: put package requirements here
]

test_requirements = [
    # TODO: put package test requirements here
]

setup(
    name='python-statemachine',
    version='0.6.2',
    description="Python Finite State Machines made easy.",
    long_description=long_description,
    author="Fernando Macedo",
    author_email='fgmacedo@gmail.com',
    url='https://github.com/fgmacedo/python-statemachine',
    packages=[
        'statemachine',
    ],
    package_dir={'statemachine':
                 'statemachine'},
    include_package_data=True,
    install_requires=requirements,
    license="MIT license",
    zip_safe=False,
    keywords='statemachine',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        "Programming Language :: Python :: 2",
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    test_suite='tests',
    tests_require=test_requirements
)
