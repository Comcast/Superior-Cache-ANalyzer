#!/usr/bin/env python3

# Copyright 2018 Comcast Cable Communications Management, LLC

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Setup script for S.C.AN.
"""

import os
from platform import system
from setuptools import setup, find_packages
from scan import __version__ as scanv

rldep = 'readline'
if system() == 'Windows':
	# Fallback dependency for Windows environment
	rldep = 'pyreadline'

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.rst')) as f:
	long_description = f.read()

setup(
	name="Superior-Cache-ANalyzer",
	version=scanv,
	description='An analysis tool for Apache Traffic Server caches.',
	long_description=long_description,
	url='https://github.com/comcast/Superior-Cache-ANalyzer',
	author='Brennan Fieck',
	author_email='Brennan_WilliamFieck@comcast.com',
	classifiers=[
		'Development Status :: 4 - Beta',
		'Intended Audience :: Telecommunications Industry',
		'Intended Audience :: Developers',
		'Intended Audience :: Information Technology',
		'Topic :: Internet',
		'Topic :: Internet :: Log Analysis',
		'Topic :: Internet :: WWW/HTTP',
		'Topic :: Scientific/Engineering :: Information Analysis',
		'Topic :: System :: Logging',
		'Topic :: Utilities',
		'License :: Other/Proprietary License',
		'Environment :: Console',
		'Operating System :: POSIX :: Linux',
		'Programming Language :: Python :: Implementation :: CPython',
		'Programming Language :: Python :: Implementation :: PyPy',
		'Programming Language :: Python :: 3 :: Only',
		'Programming Language :: Python :: 3.4',
		'Programming Language :: Python :: 3.5',
		'Programming Language :: Python :: 3.6',
		'Programming Language :: Python :: 3.7'
	],
	keywords='Apache traffic server ats cache analysis',
	packages=find_packages(exclude=['contrib', 'docs', 'tests']),
	install_requires=['setuptools', 'typing', rldep, 'numpy', 'psutil'],
	entry_points={
		'console_scripts': [
			'scan=scan.__init__:main',
		],
	},
	python_requires='~=3.4'
)
