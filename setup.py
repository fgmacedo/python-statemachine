#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function

import io

from setuptools import setup

with io.open("README.rst", encoding="utf-8") as readme_file:
    readme = readme_file.read()

long_description = readme

extras_require = {"diagrams": ["pydot"]}

setup(
    name="python-statemachine",
    version="1.0.1",
    description="Python Finite State Machines made easy.",
    long_description=long_description,
    author="Fernando Macedo",
    author_email="fgmacedo@gmail.com",
    url="https://github.com/fgmacedo/python-statemachine",
    packages=[
        "statemachine",
        "statemachine.contrib",
    ],
    package_dir={"statemachine": "statemachine"},
    extras_require=extras_require,
    include_package_data=True,
    license="MIT license",
    zip_safe=False,
    keywords="statemachine",
    classifiers=[
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Topic :: Software Development :: Libraries",
    ],
    test_suite="tests",
)
