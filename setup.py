#!/usr/bin/env python

from setuptools import setup


if __name__ == "__main__":
    setup(
        setup_requires=['pbr'],
        pbr=True, install_requires=['natsort', 'click']
    )
