#! /usr/bin/python
# -*- coding: utf-8 -*-

"""
Log extractor for Jenkins jobs
"""

import datetime
import logging
import lzma
import os
import shutil
import tempfile
import urlparse
import user
from collections import OrderedDict
from contextlib import closing

import click
from natsort import natsorted

from log_extractor import constants as const
from log_extractor import helper
from log_extractor.files import (
    TarFile,
    ZipFile,
    DirNode,
)

logger = logging.getLogger(__file__)


class LogExtractor(object):
    """
    Class to extract and parse relevant logs from the Jenkins job
    """

    def __init__(self, dst, logs):
        self.dst = dst
        self.logs = logs
        self.logs.append(const.LOG_ART_RUNNER)
        self.tss = OrderedDict()

    @staticmethod
    def _is_host_log(path):
        """
        Check if the file is host log

        Args:
            path (str): Path to the file

        Returns:
            bool: True, if the file is host log, otherwise False
        """
        for pattern in const.HOST_LOGS:
            if pattern in path:
                return True
        return False

    def _is_relevant_file(self, path):
        """
        Check if the file is relevant log

        Args:
            path (str): Path to the file

        Returns:
            bool: True, if the file is relevant log, otherwise False
        """
        for pattern in self.logs:
            if "/{0}".format(pattern) in path:
                return True
        return False

    @classmethod
    def _get_art_log_ts(cls, line):
        """
        Parse ART log timestamp

        Args:
            line (str): File line

        Returns:
            datetime: ART log timestamp
        """
        return datetime.datetime.strptime(
            line.split(" - ")[0], const.TS_FORMAT
        )

    @classmethod
    def _get_engine_log_ts(cls, line):
        """
        Get engine log timestamp

        Args:
            line (str): File line

        Returns:
            datetime: Engine log timestamp
        """
        try:
            ts = line.split()[:2]
            for ms in ("+", "-"):
                if ms in ts[1]:
                    ts[1] = ts[1].split(ms)[0]
                    break
            return datetime.datetime.strptime(" ".join(ts), const.TS_FORMAT)
        except (IndexError, ValueError, TypeError):
            return None

    @classmethod
    def _get_log_ts(cls, line):
        """
        Get log timestamp

        Args:
            line (str): File line

        Returns:
            datetime: Log timestamp
        """
        try:
            return datetime.datetime.strptime(
                line.split("::")[2], const.TS_FORMAT
            )
        except (IndexError, ValueError):
            return cls._get_engine_log_ts(line)

    @staticmethod
    def _get_host_log_prefix(file_name):
        """
        Get host log prefix

        Args:
            file_name: File name

        Returns:
            str: Host log prefix
        """
        return os.path.basename(file_name).split(".")[0]

    def _define_tss(self, test_name):
        """
        Define start, end and next test start timestamps

        Args:
            test_name (str): Test name

        Returns:
            tuple: Start, end and next test start timestamps
        """
        test_start_ts = (
            self.tss[test_name][const.TS_START] - datetime.timedelta(minutes=1)
        )
        test_end_ts = (
            self.tss[test_name][const.TS_END] + datetime.timedelta(minutes=1)
        )
        next_test_start_ts = (
            self.tss[test_name][const.TS_END] - datetime.timedelta(minutes=1)
        )
        return test_start_ts, test_end_ts, next_test_start_ts

    def _write_art_log(self, t_file, test_dir_name, ts):
        """
        Write ART log from temporary file to persist file

        Args:
            t_file (TemporaryFile): Temporary ART log file
            test_dir_name (str): Test directory name
            ts (datetime): ART log timestamp
        """
        t_file.seek(0)
        art_runner_file = os.path.join(
            test_dir_name, const.LOG_ART_RUNNER
        )
        with open(art_runner_file, "w") as new_f:
            new_f.write(t_file.read())
        t_file.close()
        self.tss[test_dir_name][const.TS_END] = ts

    @staticmethod
    def _get_team_dir_index(test_path):
        """
        Get team directory index

        Args:
            test_path (list): Test path

        Returns:
            int: Get team index from the test path
        """
        for team in const.TEAMS:
            if team in test_path:
                return test_path.index(team)
        return 0

    def _create_test_dir(self, line):
        """
        Create test directory

        Args:
            line (str): Test name line

        Returns:
            str: Test directory
        """
        test_path = line.split(": ")[-1].split(".")
        team_index = self._get_team_dir_index(
            test_path=test_path
        )
        test_path[-1] = test_path[-1].strip()
        test_dir_name = os.path.join(
            self.dst, *test_path[team_index:]
        )
        if not os.path.exists(test_dir_name):
            os.makedirs(test_dir_name)
        return test_dir_name

    def unpack_relevant_remote_logs(self, dst, source_object):
        """
        Unpacks tar.gz files containing remote logs in case they are
        inside archive.

        Args:
            dst (str): Destination path to store the extracted files
            source_object (object): Object containing log directory information
        """
        remote_dirs_all = source_object.list_files(const.REMOTE_LOGS_DIR)
        host_files = [
            x for x in remote_dirs_all
            if const.HOST_LOGS_SPEC in x.split("/")[-2]
        ]
        engine_files = [
            x for x in remote_dirs_all
            if const.ENGINE_LOG_SPEC in x.split("/")[-2]
        ]
        for log_name in self.logs:
            if log_name == const.LOG_ART_RUNNER:
                continue

            if self._is_host_log(path=log_name):
                dst_dir = "host-logs"
                remote_files = host_files
            elif log_name == const.ENGINE_LOG:
                dst_dir = "engine-logs"
                remote_files = engine_files
            dst_dir = os.path.join(dst, dst_dir)
            for f in remote_files:
                logger.info("Copying file {0} to {1}".format(f, dst_dir))
                source_object.extract(f, dst_dir)
                extension = ".".join(f.split(".")[-2:])
                os.rename(
                    os.path.join(dst_dir, os.path.basename(f)),
                    os.path.join(dst_dir, "{name}.{extension}".format(
                        name=f.split("/")[-2], extension=extension))
                )

    def parse_art_logs(self, team=None, source_object=None):
        """
        Parse art runner logs and fills the timestamps and tests variables
        """
        logger.info("==== Parse ART logs ====")
        art_runner_files_all = source_object.list_files(const.LOG_ART_DIR)
        art_runner_files = []
        for art_logs in (const.LOG_ART_RUNNER_DEBUG, const.LOG_ART_RUNNER):
            art_runner_files = [
                f for f in art_runner_files_all if art_logs in f]
            if art_runner_files:
                break

        if not art_runner_files:
            raise RuntimeError("Failed to find ART runner logs.")

        art_runner_files = natsorted(art_runner_files, reverse=True)

        t_file = None
        ts = None
        last_ts = None
        test_dir_name = None
        relevant_team = False
        start_write = False
        stop_parsing = False
        line = None

        for art_runner_file in art_runner_files:
            logger.info("parse file {0}".format(art_runner_file))
            with source_object.open(art_runner_file) as f:
                for line in f:
                    setup_line = any(s in line for s in const.FIELDS_SETUP)
                    if setup_line:
                        ts = self._get_art_log_ts(line=line)
                        start_write = True
                        if t_file and not t_file.closed:
                            self._write_art_log(
                                t_file=t_file,
                                test_dir_name=test_dir_name,
                                ts=ts
                            )
                        t_file = tempfile.TemporaryFile(mode="w+")

                    if t_file and not t_file.closed and start_write:
                        t_file.write(line)

                    if const.FIELD_TEST_NAME in line:
                        if (
                            team is None or ".{0}.".format(team) in line
                        ) and ts:
                            relevant_team = True
                            test_dir_name = self._create_test_dir(line=line)
                            self.tss[test_dir_name] = {}
                            self.tss[test_dir_name][const.TS_START] = ts
                        else:
                            if t_file and not t_file.closed:
                                t_file.close()
                            if relevant_team:
                                stop_parsing = True
                                break

                    teardown_line = any(
                        t in line for t in const.FIELDS_TEARDOWN
                    )
                    if teardown_line and relevant_team:
                        last_ts = self._get_art_log_ts(line)

            if stop_parsing:
                break

        if not last_ts and line:
            last_ts = self._get_art_log_ts(line)

        if t_file and not t_file.closed:
            self._write_art_log(
                t_file=t_file, test_dir_name=test_dir_name, ts=last_ts
            )

    def parse_logs(self):
        """
        Parse engine and hosts logs by timestamps and tests variables
        """
        if not self.tss:
            raise RuntimeError("You need to run parse_art_logs first")

        cur_t_file = None
        tests_iter = None
        cur_test_name = None
        start_ts = None
        end_ts = None
        next_start_ts = None
        temp_log_name = ""
        stop_parsing = False
        start_write = False
        next_test_f_pos = None

        for log_name in self.logs:
            if log_name == const.LOG_ART_RUNNER:
                continue

            logger.info("==== Parse {0}'s ====".format(log_name))

            log_files = []
            if self._is_host_log(path=log_name):
                search_dir = "host-logs"
            else:
                search_dir = "engine-logs"
            search_dir = os.path.join(self.dst, const.TEMPDIR_NAME, search_dir)

            for (dirpath, _, filenames) in os.walk(search_dir):
                for tarfile in filenames:
                    tar_object = TarFile(os.path.join(dirpath, tarfile))
                    log_files += [
                        (tarfile, x, tar_object)
                        for x in tar_object.list_files()
                        if os.path.basename(x).startswith(log_name)
                    ]
                break

            if not log_files:
                continue

            log_files = natsorted(log_files, reverse=True)
            if log_name == const.ENGINE_LOG:
                log_files = natsorted(log_files)
                log_files.insert(len(log_files) - 1, log_files.pop(0))

            log_prefix = ""
            temp_log_prefix = ""
            for tarfile, log_file, tar_object in log_files:
                logger.info(
                    "parse file {0} from {1}".format(log_file, tarfile)
                )
                new_file_name = log_name
                write_next_test_f_pos = True
                if self._is_host_log(path=log_name):
                    log_prefix = self._get_host_log_prefix(file_name=tarfile)
                    new_file_name = "{0}_{1}".format(log_prefix, new_file_name)
                if (
                    (temp_log_name != log_name) or
                    (log_prefix != temp_log_prefix)
                ):
                    tests_iter = iter(self.tss.keys())
                    cur_test_name = tests_iter.next()
                    start_ts, end_ts, next_start_ts = self._define_tss(
                        test_name=cur_test_name
                    )
                    if cur_t_file and not cur_t_file.closed:
                        cur_t_file.close()
                    cur_t_file = tempfile.TemporaryFile(mode="w+")
                    start_write = False
                    stop_parsing = False
                    temp_log_name = log_name
                    temp_log_prefix = log_prefix

                if stop_parsing:
                    continue

                with closing(tar_object.open(log_file)) as f:
                    f_pos = f.tell()
                    line = f.readline()
                    while line:
                        ts = self._get_log_ts(line)
                        if (
                            (not ts and start_write) or
                            (ts and start_ts <= ts <= end_ts)
                        ):
                            start_write = True
                            cur_t_file.write(line)
                            if (
                                ts and ts >= next_start_ts and
                                write_next_test_f_pos
                            ):
                                next_test_f_pos = f_pos
                                write_next_test_f_pos = False
                        elif start_write or (ts and end_ts < ts):
                            new_file_path = os.path.join(
                                cur_test_name, new_file_name
                            )
                            with open(new_file_path, "w") as new_f:
                                cur_t_file.seek(0)
                                new_f.write(cur_t_file.read())
                            cur_t_file.close()
                            try:
                                cur_test_name = tests_iter.next()
                            except StopIteration:
                                stop_parsing = True
                                break
                            start_write = False
                            f.seek(next_test_f_pos)
                            write_next_test_f_pos = True
                            start_ts, end_ts, next_start_ts = self._define_tss(
                                test_name=cur_test_name
                            )
                            cur_t_file = tempfile.TemporaryFile(mode="w+")

                        f_pos = f.tell()
                        try:
                            line = f.readline()
                        except lzma.error:
                            break


@click.command()
@click.option(
    "--source",
    help=(
        "Source for the logs to refactor. Can be Jenkins build url,"
        "locally downloaded file from Jenkins jobs artifacts (archive.zip), "
        "or path to directory containing the logs, exactly in the format "
        "they are in Jenkins Job $WORKSPACE."
    ),
    required=True
)
@click.option(
    "--folder",
    help=(
        "Folder path to save the logs. In case source is url,"
        "the job name and build number will be appended to folder name."
    ),
    default=os.path.join(user.home, "art-tests-logs")
)
@click.option(
    "--logs",
    help=(
        "List of logs to parse(vdsm.log,engine.log,...), "
        "if you do not specify logs it will use default logs %s" %
        const.DEFAULT_LOGS
    )
)
@click.option(
    "--team",
    type=click.Choice(const.TEAMS),
    help=(
        "Team logs to parse, if you do not specify the "
        "team it will parse log for all teams"
    )
)
@click.option(
    "--log-output", help="Redirect output to a file."
)
@click.option(
    "-v", "--verbose", count=True,
    help="Increases log verbosity for each occurence.", default=0
)
def run(source, folder, logs, team, log_output, verbose):
    """
    Restructure logs from Jenkins jobs.
    """
    helper.configure_logging(log_output=log_output, verbose=verbose)

    if not os.path.exists(path=folder):
        os.makedirs(folder)

    source_type = helper.identify_source_type(source)
    source_path = source

    if source_type == "url":
        parsed_url = urlparse.urlparse(source)
        jenkins_path_list = parsed_url.path.split("/")
        job_name = jenkins_path_list[2]
        build_number = jenkins_path_list[3]
        folder = os.path.join(folder, job_name, build_number)
        source_path = os.path.join(
            folder, const.TEMPDIR_NAME,
            "{filename}.zip".format(filename=const.JOB_ARTIFACT)
        )
        helper.download_artifact(job_url=source, dst=os.path.join(source_path))
        source_type = "zip"
        source = source_path

    if source_type == "dir":
        folder = source
        source_object = DirNode(source_path)
    elif source_type == "zip":
        folder = os.path.dirname(source)
        source_object = ZipFile(source_path)
    else:
        err = "The source logs files are of unhandled type."
        raise Exception(err)

    build_folder = os.path.join(folder, const.TEMPDIR_NAME)
    logs = logs.split(",") if logs else const.DEFAULT_LOGS

    log_extractor = LogExtractor(dst=folder, logs=logs)
    log_extractor.parse_art_logs(team=team, source_object=source_object)
    log_extractor.unpack_relevant_remote_logs(
        dst=build_folder, source_object=source_object
    )
    log_extractor.parse_logs()
    if os.path.isdir(build_folder):
        shutil.rmtree(build_folder)

    logger.info("Logs was extracted to {folder}".format(folder=folder))


if __name__ == "__main__":
    run()
