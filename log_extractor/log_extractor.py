#! /usr/bin/python
# -*- coding: utf-8 -*-

"""
Log extractor for Jenkins jobs
"""

import datetime
import glob
import os
import re
import shutil
import ssl
import tempfile
import user
from collections import OrderedDict

import click
import jenkins as jenkins_api
import pyunpack
from natsort import natsorted

import constants as const
import helper


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
            if '/{0}'.format(pattern) in path:
                return True
        return False

    def _generate_host_log_name(self, path):
        """
        Generate host log name, hostname_logname.log

        Args:
            path (str): Path to the host file

        Returns:
            str: New host log name
        """
        f_basename = os.path.basename(path)
        next_dir = False
        prefix = ''
        for dir_name in path.split('/'):
            if next_dir and dir_name not in ['logs', 'hosts-logs']:
                prefix = dir_name
                break
            if dir_name in ['logs', 'hosts-logs']:
                next_dir = True
        f_new_basename = "{0}_{1}".format(prefix, f_basename)
        return os.path.join(self.dst, f_new_basename)

    def extract_all(self, path):
        """
        Extract recursively all archives under the path directory and
        copy all relevant files to the path directory

        Args:
            path (str): Path to the directory
        """
        for root, dirs, files in os.walk(path):
            for f in files:
                f_path = os.path.join(root, f)
                if (
                    not os.path.islink(f_path) and
                    helper.is_archive(f_path) and
                    os.path.getsize(f_path) != 0
                ):
                    dst_path = os.path.splitext(f_path)[0]
                    print '==== Unpack the file %s ====' % f_path
                    pyunpack.Archive(f_path).extractall(
                        dst_path, auto_create_dir=True
                    )
                    f_path = dst_path
                    if os.path.isdir(f_path):
                        self.extract_all(f_path)
                if os.path.isfile(f_path) and self._is_relevant_file(f_path):
                    dst_path = os.path.join(self.dst, os.path.basename(f_path))
                    if self._is_host_log(f_path):
                        dst_path = self._generate_host_log_name(f_path)
                    if f_path != dst_path and not helper.is_archive(f_path):
                        shutil.copy(f_path, dst_path)

            if dirs:
                for dir_name in dirs:
                    self.extract_all(dir_name)

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
            line.split(' - ')[0], const.TS_FORMAT
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
            for ms in ('+', '-'):
                if ms in ts[1]:
                    ts[1] = ts[1].split(ms)[0]
                    break
            return datetime.datetime.strptime(' '.join(ts), const.TS_FORMAT)
        except (IndexError, ValueError):
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
                line.split('::')[2], const.TS_FORMAT
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
        return os.path.basename(file_name).split('_')[0]

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
        with open(art_runner_file, 'w') as new_f:
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

        """
        test_path = line.split(': ')[-1].split('.')
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

    def parse_art_logs(self, team=None):
        """
        Parse art runner logs and fills the timestamps and tests variables
        """
        print '==== Parse ART logs ===='

        art_runner_files = []
        for art_logs in (const.LOG_ART_RUNNER_DEBUG, const.LOG_ART_RUNNER):
            art_runner_files = glob.glob('{0}/{1}*'.format(self.dst, art_logs))
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
            print 'parse file {0}'.format(art_runner_file)
            with open(art_runner_file) as f:
                for line in f:
                    if re.findall(const.PATTERN_SETUP, line):
                        ts = self._get_art_log_ts(line=line)
                        start_write = True
                        if t_file and not t_file.closed:
                            self._write_art_log(
                                t_file=t_file,
                                test_dir_name=test_dir_name,
                                ts=ts
                            )
                        t_file = tempfile.TemporaryFile(mode='w+')

                    if t_file and not t_file.closed and start_write:
                        t_file.write(line)

                    if const.FIELD_TEST_NAME in line:
                        if (
                            team is None or '.{0}.'.format(team) in line
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

                    if re.findall(
                        const.PATTERN_TEARDOWN, line
                    ) and relevant_team:
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
        next_t_file = None
        tests_iter = None
        cur_test_name = None
        start_ts = None
        end_ts = None
        next_start_ts = None
        temp_log_name = ''
        stop_parsing = False
        start_write = False

        for log_name in self.logs:
            if log_name == const.LOG_ART_RUNNER:
                continue

            print '==== Parse {0}\'s ===='.format(log_name)

            search_pattern = '{0}/{1}*'
            if self._is_host_log(path=log_name):
                search_pattern = '{0}/*_{1}*'
            log_files = glob.glob(search_pattern.format(self.dst, log_name))
            if not log_files:
                continue

            log_files = natsorted(log_files, reverse=True)
            if log_name == const.LOG_ENGINE:
                log_files = natsorted(log_files)
                log_files.insert(len(log_files) - 1, log_files.pop(0))

            log_prefix = ''
            temp_log_prefix = ''
            for log_file in log_files:
                print 'parse file {0}'.format(log_file)
                new_file_name = log_name
                if self._is_host_log(path=log_name):
                    log_prefix = self._get_host_log_prefix(file_name=log_file)
                    new_file_name = '{0}_{1}'.format(log_prefix, new_file_name)
                if (
                    (temp_log_name != log_name) or
                    (log_prefix != temp_log_prefix)
                ):
                    tests_iter = iter(self.tss.keys())
                    cur_test_name = tests_iter.next()
                    if cur_t_file and not cur_t_file.closed:
                        cur_t_file.close()
                    if next_t_file and not next_t_file.closed:
                        next_t_file.close()
                    cur_t_file = tempfile.TemporaryFile(mode='w+')
                    next_t_file = tempfile.TemporaryFile(mode='w+')
                    start_ts, end_ts, next_start_ts = self._define_tss(
                        test_name=cur_test_name
                    )
                    start_write = False
                    stop_parsing = False
                    temp_log_name = log_name
                    temp_log_prefix = log_prefix

                if stop_parsing:
                    continue

                with open(log_file) as f:
                    for line in f:
                        ts = self._get_log_ts(line)
                        if (
                            (not ts and start_write) or
                            (ts and start_ts <= ts <= end_ts)
                        ):
                            start_write = True
                            cur_t_file.write(line)
                            if ts and ts >= next_start_ts:
                                next_t_file.write(line)
                        elif start_write:
                            new_file_path = os.path.join(
                                cur_test_name, new_file_name
                            )
                            with open(new_file_path, 'w') as new_f:
                                cur_t_file.seek(0)
                                new_f.write(cur_t_file.read())
                            cur_t_file.close()
                            try:
                                cur_test_name = tests_iter.next()
                            except StopIteration:
                                stop_parsing = True
                                next_t_file.close()
                                break
                            next_t_file.write(line)
                            cur_t_file = next_t_file
                            next_t_file = tempfile.TemporaryFile(mode='w+')
                            start_ts, end_ts, next_start_ts = self._define_tss(
                                test_name=cur_test_name
                            )


@click.command()
@click.option(
    "--job", cls=helper.MutuallyExclusiveOption,
    mutually_exclusive=["skip_download", "local_log_file"],
    help="Job name"
)
@click.option(
    "--build", cls=helper.MutuallyExclusiveOption,
    mutually_exclusive=["skip_download", "local_log_file"],
    help="build number of the job", type=int
)
@click.option(
    "--folder",
    help="Folder path to save the logs",
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
    "--skip-download", is_flag=True, cls=helper.MutuallyExclusiveOption,
    mutually_exclusive=["job", "build"],
    help=(
        "In case of pre-downloaded logs we can skip download."
        "Must be used with local-log-file option."
        "In case logs folder already contains compressed log file, "
        "it will be used and download will be skipped automatically."

    )
)
@click.option(
    "--local-log-file", cls=helper.MutuallyExclusiveOption,
    mutually_exclusive=["job", "build"],
    help=(
        "In case that skip-download is True we can provide path to "
        "local compressed file with the logs."
    )
)
@click.option(
    "--clean/--no-clean",
    help="Clean all unarchived files after the parsing",
    default=True
)
def run(job, build, folder, logs, team, skip_download, local_log_file, clean):
    """
    Extract and restructure logs from Jenkins jobs.
    """
    def get_jenkins_connection():
        """
        Get Jenkins connection object

        Returns:
            Jenkins: Jenkins connection
        """
        ssl._create_default_https_context = ssl._create_unverified_context
        return jenkins_api.Jenkins(url=helper.get_jenkins_server())

    def check_for_existing_logs_file(path):
        """
        Get folder that logs are supposed to be extracted and
        check for compressed files that might contain the Jenkins logs.

        Returns:
            bool: True if log file if found else False
        """
        found_local_logs = False
        for root, dirs, files in os.walk(path):
            if found_local_logs:
                break
            for f in files:
                f_path = os.path.join(root, f)
                if (
                    not os.path.islink(f_path) and
                    helper.is_archive(f_path) and
                    os.path.getsize(f_path) != 0
                ):
                    print(
                        "Compressed log file found under {folder}."
                        "Will skip download of logs from Jenkins.".format(
                            folder=path)
                    )
                    found_local_logs = True
                    break
        return found_local_logs

    if not os.path.exists(path=folder):
        os.mkdir(folder)

    found_local_logs = check_for_existing_logs_file(folder)

    if not skip_download and not found_local_logs:
        jenkins_connection = get_jenkins_connection()
        build_info = jenkins_connection.get_build_info(name=job, number=build)
        job_url = build_info.get("url")

        job_folder = os.path.join(folder, job)
        if not os.path.exists(path=job_folder):
            os.mkdir(job_folder)

        build_folder = os.path.join(job_folder, str(build))
        if not os.path.exists(path=build_folder):
            os.mkdir(build_folder)

        helper.download_artifact(job_url=job_url, dst=build_folder)
    else:
        print "Skipping download artifacts..."

        build_folder = folder
        if found_local_logs:
            print "Using existing log file found in {folder}".format(
                folder=build_folder)
        else:
            logs_dir_name = os.path.basename(local_log_file)
            logs_link_name = os.path.join(build_folder, logs_dir_name)
            if not os.path.exists(logs_link_name):
                print "Creating hardlink for {log_dir} to {folder}".format(
                    folder=logs_link_name, log_dir=local_log_file)
                os.link(local_log_file, logs_link_name)

    logs = logs.split(",") if logs else const.DEFAULT_LOGS
    log_extractor = LogExtractor(dst=build_folder, logs=logs)
    log_extractor.extract_all(path=build_folder)
    log_extractor.parse_art_logs(team=team)
    log_extractor.parse_logs()
    print "Logs was extracted to {folder}".format(folder=build_folder)
    if clean:
        helper.remove_unarchived_files(build_folder)


if __name__ == "__main__":
    run()
