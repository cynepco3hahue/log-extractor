#! /usr/bin/python
# -*- coding: utf-8 -*-

"""
Constants for log-extractor
"""

import os
import user

JOB_ARTIFACT = 'artifact'
JOB_ARTIFACT_ZIP = '{0}/*zip*/archive.zip'.format(JOB_ARTIFACT)
ARCHIVE_EXTENSIONS = ['.gz', '.zip', '.xz', '.tar', '.bz2']
TEAMS = ['compute', 'networking', 'storage', 'system', 'coresystem', 'sla', 'virt']
FIELD_TEST_NAME = 'Test Name'
FIELD_SETUP = 'SETUP <'
FIELD_TEARDOWN = 'TEARDOWN <'
LOG_ART_RUNNER_DEBUG = 'art_test_runner.log.debug'
LOG_ART_RUNNER = 'art_test_runner.log'
LOG_ENGINE = 'engine.log'
TS_FORMAT = '%Y-%m-%d %H:%M:%S,%f'
TS_START = 'start_timestamp'
TS_END = 'end_timestamp'
HOST_LOGS = ["vdsm.log", "supervdsm.log"]
DEFAULT_LOGS = HOST_LOGS + [LOG_ENGINE]
JENKINS_CONF = os.path.join(user.home, ".jenkins.config")
