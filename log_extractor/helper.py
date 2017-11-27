#! /usr/bin/python
# -*- coding: utf-8 -*-

"""
Helper file for the log extractor
"""
import ConfigParser
import os
import shutil
import tarfile
import logging
import pycurl

import constants as const
from click import Option, UsageError

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


def get_jenkins_server():
    """
    Get jenkins server from config file
    """
    config = ConfigParser.RawConfigParser()
    config.read(const.JENKINS_CONF)
    return config.get("SETTING", "server")


def is_archive(path):
    """
    Check if the file is archive

    Args:
        path (str): Path to the file

    Returns:
        bool: True, if the file is archive, otherwise False
    """
    f_ext = os.path.splitext(path)[1]
    return f_ext in const.ARCHIVE_EXTENSIONS or tarfile.is_tarfile(path)


class MutuallyExclusiveOption(Option):
    def __init__(self, *args, **kwargs):
        """
        Adding support for mutually exclusive parameters in click.Option
        """
        self.mutually_exclusive = set(kwargs.pop('mutually_exclusive', []))
        help = kwargs.get('help', '')
        if self.mutually_exclusive:
            ex_str = ', '.join(self.mutually_exclusive)
            kwargs['help'] = help + (
                ' NOTE: This argument is mutually exclusive with '
                ' arguments: [' + ex_str + '].'
            )
        super(MutuallyExclusiveOption, self).__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        """
        We are overriding here the click.Option.handle_parse_result() method
        to raise Error in cause mutually exclusive parameters are used
        together.
        """
        if self.mutually_exclusive.intersection(opts) and self.name in opts:
            raise UsageError(
                "Illegal usage: `{}` is mutually exclusive with "
                "arguments `{}`.".format(
                    self.name,
                    ', '.join(self.mutually_exclusive)
                )
            )

        return super(MutuallyExclusiveOption, self).handle_parse_result(
            ctx,
            opts,
            args
        )


def remove_unarchived_files(build_folder):
    """
    Remove all unarchived files from the build directory after the parsing

    Args:
        build_folder (str): Build folder
    """
    print "Remove unarchived files from the folder {0}".format(build_folder)
    for f in os.listdir(build_folder):
        f_path = os.path.join(build_folder, f)
        if os.path.isfile(f_path):
            os.remove(f_path)
        elif f == "artifact":
            shutil.rmtree(f_path)
