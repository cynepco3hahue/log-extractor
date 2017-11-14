#! /usr/bin/python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

SCRIPT_NAME = "log-extractor"
SCRIPT = (
    "_JLOG_EXTRACTOR_COMPLETE=source {script_name} > "
    "auto-completion.sh".format(script_name=SCRIPT_NAME)
)

setup(
    name='log_extractor',
    version='1.0',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'Click',
        'pyunpack',
        'natsort',
        'jenkinsapi',
        'python-jenkins',
        'patool',
        'pycurl'
    ],
    entry_points='''
        [console_scripts]
        {script_name}=log_extractor.log_extractor:run
    '''.format(script_name=SCRIPT_NAME),
)
