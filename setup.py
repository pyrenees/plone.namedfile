# -*- coding: utf-8 -*-
from setuptools import find_packages
from setuptools import setup
import os
import sys


version = '4.0.0.dev0'
description = 'File types and fields for images, files and blob files with ' \
              'filenames'
long_description = ('\n\n'.join([
    open('README.rst').read(),
    open('CHANGES.rst').read(),
    open(os.path.join("plone", "namedfile", "usage.rst")).read(),
]))


setup(
    name='plone.namedfile',
    version=version,
    description=description,
    long_description=long_description,
    classifiers=[
        "Framework :: Plone",
        "Framework :: Plone :: 5.1",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: BSD License",
    ],
    keywords='plone named file image blob',
    author='Laurence Rowe, Martin Aspeli',
    author_email='plone-developers@lists.sourceforge.net',
    url='https://pypi.python.org/pypi/plone.namedfile',
    license='BSD',
    packages=find_packages(exclude=['ez_setup']),
    namespace_packages=['plone'],
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'persistent',
        'plone.rfc822',
        'plone.scale',
        'plone.supermodel',
        'python-dateutil',
        'setuptools',
        'zope.annotation',
        'zope.browserpage',
        'zope.component',
        'zope.copy',
        'zope.security',
        'zope.traversing',
    ],
    extras_require={
        'test': [
            'lxml',
            'Pillow',
            'plone.testing',
            'ZODB',
        ]
    },
)
