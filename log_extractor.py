"""

"""
# encoding=utf8
import os
import glob
import tarfile
import shutil
import tempfile
import pyunpack
import datetime
from natsort import natsorted
from collections import OrderedDict

import constants as const
import helper

TEST_URL = "https://rhev-jenkins.rhev-ci-vms.eng.rdu2.redhat.com/job/rhv-master-ge-runner-tier2/12/"
TEST_DST = "/home/alukiano/test_arc"
TEST_LOGS = ["vdsm.log", "engine.log", "supervdsm.log"]
HOST_SPECIFIC_LOGS = ["vdsm.log", "supervdsm.log"]


class Version(object):
    """

    """
    def __init__(self, version):
        """

        Args:
            version:
        """
        self.major, self.minor = version.split('.')


class LogExtractor(object):
    """

    """
    def __init__(self, dst, logs):
        self.dst = dst
        self.logs = logs
        self.logs.append(const.LOG_ART_RUNNER)
        self.tss = OrderedDict()

    @staticmethod
    def _is_archive(path):
        """

        Args:
            path:

        Returns:

        """
        f_ext = os.path.splitext(path)[1]
        return f_ext in const.ARCHIVE_EXTENSIONS or tarfile.is_tarfile(path)

    @staticmethod
    def _is_host_log(path):
        """

        Args:
            path:

        Returns:

        """
        for pattern in HOST_SPECIFIC_LOGS:
            if pattern in path:
                return True
        return False

    def _is_relevant_file(self, path):
        """

        Args:
            path:

        Returns:

        """
        for pattern in self.logs:
            if '/{0}'.format(pattern) in path:
                return True
        return False

    @staticmethod
    def _generate_host_log_name(path):
        """

        Args:
            path:

        Returns:

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
        return os.path.join(TEST_DST, f_new_basename)

    def extract_all(self, path):
        """

        Args:
            path:

        Returns:

        """
        for root, dirs, files in os.walk(path):
            for f in files:
                f_path = os.path.join(root, f)
                if self._is_archive(f_path) and os.path.getsize(f_path) != 0:
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
                    if f_path != dst_path and not self._is_archive(f_path):
                        shutil.copy(f_path, dst_path)
            if dirs:
                for dir_name in dirs:
                    self.extract_all(dir_name)

    @classmethod
    def _get_art_log_ts(cls, line):
        """

        Args:
            line (str):

        Returns:

        """
        return datetime.datetime.strptime(
            line.split(' - ')[0], const.TS_FORMAT
        )

    @classmethod
    def _get_engine_log_ts(cls, line):
        """

        Args:
            line:

        Returns:

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

        Args:
            line:

        Returns:

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

        Args:
            file_name:

        Returns:

        """
        return os.path.basename(file_name).split('_')[0]

    def _define_tss(self, test_name):
        """

        Args:
            test_name:

        Returns:

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

        Args:
            t_file:
            test_dir_name:
            ts:

        Returns:

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

        Args:
            test_path:

        Returns:

        """
        for team in const.TEAMS:
            if team in test_path:
                return test_path.index(team)
        return 0

    def _create_test_dir(self, line):
        """

        Args:
            line:

        Returns:

        """
        test_path = line.split(' - ')[-1].split('.')
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
        art_runner_files = glob.glob(
            '{0}/{1}*'.format(self.dst, const.LOG_ART_RUNNER)
        )
        art_runner_files = natsorted(art_runner_files, reverse=True)
        start_write = False
        t_file = None
        ts = None
        last_ts = None
        test_dir_name = None
        relevant_team = False
        stop_parsing = False
        for art_runner_file in art_runner_files:
            print 'parse file %s' % art_runner_file
            with open(art_runner_file) as f:
                for line in f:
                    if const.FIELD_SETUP in line:
                        ts = self._get_art_log_ts(line=line)
                        start_write = True
                        if test_dir_name:
                            self._write_art_log(
                                t_file=t_file,
                                test_dir_name=test_dir_name,
                                ts=ts
                            )
                        if t_file:
                            t_file.close()
                        t_file = tempfile.TemporaryFile(mode='w+')

                    if start_write:
                        t_file.write(line)

                    if const.FIELD_TEST_NAME in line:
                        if team is None or team in line:
                            relevant_team = True
                            test_dir_name = self._create_test_dir(line=line)
                            self.tss[test_dir_name] = {}
                            self.tss[test_dir_name][const.TS_START] = ts
                        else:
                            if relevant_team:
                                stop_parsing = True
                                break
                            relevant_team = False
                            test_dir_name = None

                    if const.FIELD_TEARDOWN in line and relevant_team:
                        last_ts = self._get_art_log_ts(line)

            if stop_parsing:
                break

        if test_dir_name:
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
        for log in self.logs:
            if log == const.LOG_ART_RUNNER:
                continue

            print '==== Parse %s\'s ====' % log

            search_pattern = '{0}/{1}*'
            if self._is_host_log(path=log):
                search_pattern = '{0}/*_{1}*'
            log_files = glob.glob(search_pattern.format(self.dst, log))
            log_files = natsorted(log_files, reverse=True)
            if log == const.LOG_ENGINE:
                log_files = natsorted(log_files)
                log_files.insert(len(log_files) - 1, log_files.pop(0))

            tests_iter = iter(self.tss.keys())
            cur_test_name = tests_iter.next()

            if cur_t_file:
                cur_t_file.close()
            if next_t_file:
                next_t_file.close()
            cur_t_file = tempfile.TemporaryFile(mode='w+')
            next_t_file = tempfile.TemporaryFile(mode='w+')
            start_ts, end_ts, next_start_ts = self._define_tss(
                test_name=cur_test_name
            )
            start_write = False
            stop_parsing = False

            log_prefix = ''
            temp_log_prefix = ''
            for log_file in log_files:
                print 'parse file %s' % log_file
                new_file_name = log
                if self._is_host_log(path=log):
                    log_prefix = self._get_host_log_prefix(file_name=log_file)
                    new_file_name = '{0}_{1}'.format(log_prefix, new_file_name)
                if temp_log_prefix and log_prefix != temp_log_prefix:
                    tests_iter = iter(self.tss.keys())
                    cur_test_name = tests_iter.next()
                    if cur_t_file:
                        cur_t_file.close()
                    if next_t_file:
                        next_t_file.close()
                    cur_t_file = tempfile.TemporaryFile(mode='w+')
                    next_t_file = tempfile.TemporaryFile(mode='w+')
                    start_ts, end_ts, next_start_ts = self._define_tss(
                        test_name=cur_test_name
                    )
                    start_write = False
                    stop_parsing = False
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


# helper.download_artifact(job_url=TEST_URL, dst=TEST_DST)
log_extractor = LogExtractor(TEST_DST, logs=TEST_LOGS)
# log-extractor.extract_all(path=TEST_DST)
log_extractor.parse_art_logs()
log_extractor.parse_logs()
