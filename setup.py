#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function

import io
from setuptools import setup

with io.open('README.rst', encoding='utf-8') as readme_file:
    readme = readme_file.read()

with io.open('HISTORY.rst', encoding='utf-8') as history_file:
    history = history_file.read()

long_description = readme + '\n\n' + history


setup(
    name='python-statemachine',
    version='0.8.0',
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
    license="MIT license",
    zip_safe=False,
    keywords='statemachine',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        "Programming Language :: Python :: 2",
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Topic :: Software Development :: Libraries',
    ],
    test_suite='tests'
)
