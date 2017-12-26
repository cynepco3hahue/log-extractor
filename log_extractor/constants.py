#! /usr/bin/python
# -*- coding: utf-8 -*-

"""
Constants for log-extractor
"""

JOB_ARTIFACT = 'artifact'
JOB_ARTIFACT_ZIP = '{0}/*zip*/archive.zip'.format(JOB_ARTIFACT)
ARTIFACT_ZIP_NAME = "archive.zip"

TEAMS = ['compute', 'networking', 'storage',
         'system', 'coresystem', 'sla', 'virt']

FIELD_TEST_NAME = 'Test Name'
FIELDS_SETUP = ('SETUP <', '--TEST START--')
FIELDS_TEARDOWN = ('TEARDOWN <', '--TEST END--')

TS_FORMAT = '%Y-%m-%d %H:%M:%S,%f'
TS_START = 'start_timestamp'
TS_END = 'end_timestamp'

LOG_ART_RUNNER_DEBUG = 'art_test_runner.log.debug'
LOG_ART_RUNNER = 'art_test_runner.log'
LOG_ART_DIR = 'logs'

REMOTE_LOGS_DIR = "ansible-playbooks/playbooks/ovirt-collect-logs/logs/"
ENGINE_LOG = 'engine.log'
ENGINE_LOG_SPEC = "engine"
HOST_LOGS = ["vdsm.log", "supervdsm.log"]
HOST_LOGS_SPEC = "hypervisor"

DEFAULT_LOGS = HOST_LOGS + [ENGINE_LOG]

TEMPDIR_NAME = "tempdir"
