#! /usr/bin/python
# -*- coding: utf-8 -*-

"""
Helper file for the log extractor
"""
import os
import logging
import pycurl
from urllib2 import urlopen

import constants as const

logger = logging.getLogger(__file__)


def download_artifact(job_url, dst):
    """
    Download artifact archive from the jenkins to the destination path

    Args:
        job_url (str): URL on the job
        dst (str): Destination path
    """
    dst_path = dst
    if os.path.isdir(dst):
        dst_path = os.path.join(dst, "%s.zip" % const.JOB_ARTIFACT)

    if not os.path.exists(os.path.dirname(dst_path)):
        os.makedirs(os.path.dirname(dst_path))

    with open(dst_path, 'wb') as f:
        conn = pycurl.Curl()
        conn.setopt(conn.SSL_VERIFYHOST, False)
        conn.setopt(conn.SSL_VERIFYPEER, False)
        conn.setopt(conn.URL, str("%s/%s" % (job_url, const.JOB_ARTIFACT_ZIP)))
        conn.setopt(conn.WRITEDATA, f)
        logger.info("Download artifacts from the link %s", job_url)
        conn.perform()
        conn.close()


def identify_source_type(source):
    """
    Identifies source type, can be URL, ZIP file or directory.

    Returns:
        string: "url", "zip", "dir"
    """
    try:
        f = urlopen(source)
        f.close()
        return "url"
    except ValueError:
        if os.path.basename(source) == const.ARTIFACT_ZIP_NAME:
            return "zip"
        elif os.path.isdir(source):
            return "dir"


def configure_logging(log_output, verbose):
    """
    Configures python logging.

    Args:
        log_output (str): Filename to redirect output to.
                          If None stdout will be used.
    """
    log_levels = [logging.WARNING, logging.INFO, logging.DEBUG]
    log_level = log_levels[min(len(log_levels)-1, verbose)]

    logging.basicConfig(
        filename=log_output,
        stream=None,
        level=log_level
    )
