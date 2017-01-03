"""
Helper file for the log extractor
"""
import os
import constants as const
import pycurl


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
        conn.setopt(conn.URL, "%s/%s" % (job_url, const.JOB_ARTIFACT_ZIP))
        conn.setopt(conn.WRITEDATA, f)
        conn.perform()
        conn.close()
