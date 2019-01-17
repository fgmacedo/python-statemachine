#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function

from setuptools import setup

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

long_description = readme + '\n\n' + history


requirements = []

test_requirements = []

setup(
    name='python-statemachine',
    version='0.7.1',
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
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        "Programming Language :: Python :: 2",
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Software Development :: Libraries',
    ],
    test_suite='tests',
    tests_require=test_requirements
)
