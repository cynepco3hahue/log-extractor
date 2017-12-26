import gzip
import lzma
import os
import tarfile
import zipfile


class TarFile(object):
    """
    Class to abstract operations like list, open on tar files
    """

    def __init__(self, path):
        self.path = path
        self.tf = tarfile.open(path, 'r:gz')

    def list_files(self):
        """
        List all members of TarFile current object

        Returns:
            list: Names of members of ZipFile object
        """
        return self.tf.getnames()

    def open(self, filepath):
        """
        Extracts a member from the archive as a file-like object.
        In case file is LZMA in uncompressed as well.

        Args:
            filepath (str): File object

        Returns:
            file-like object for 'filepath'
        """
        if filepath.endswith(".xz") or filepath.endswith("gz"):
            dir_base = os.path.dirname(self.path)
            dir_name = os.path.basename(self.path).split(".")[0]
            dir_path = os.path.join(dir_base, dir_name)
            extracted_filepath = os.path.join(dir_path, filepath)
            if not os.path.exists(dir_path):
                os.mkdir(dir_path)
            self.tf.extract(filepath, dir_path)
            if filepath.endswith(".xz"):
                return lzma.LZMAFile(extracted_filepath)

            if filepath.endswith(".gz"):
                return gzip.open(
                    extracted_filepath, "r:gz"
                )

        return self.tf.extractfile(filepath)

    def extract(self, filepath, dst):
        """
        Extract a member from the archive to the dst folder

        Args:
            filepath (str): Filename of the member of the archive to extract
            dst (str): Destination folder to extract the archive.
        """
        self.tf.extract(filepath, dst)


class ZipFile(object):
    """
    Class to abstract operations like list, open on zip files
    """

    def __init__(self, path):
        self.path = path
        self.zf = zipfile.ZipFile(path, 'r')

    def list_files(self, directory):
        """
        List all files of ZipFile current object that are in `directory` path

        Args:
            directory (str): Directory path to limit returned files

        Returns:
            list: Names of members of ZipFile object within `directory`
        """
        return [x for x in self.zf.namelist() if directory in x]

    def open(self, filepath):
        """
        Extracts a member from the archive as a file-like object.

        Args:
            filepath (str): File object

        Returns:
            file-like object for 'filepath'
        """
        return self.zf.open(filepath, 'r')

    def extract(self, filepath, dst):
        """
        Extract a member from the archive to the dst folder

        Args:
            filepath (str): Filename of the member of the archive to extract
            dst (str): Destination folder to extract the archive.
        """
        self.zf.extract(filepath, dst)
        os.rename(
            os.path.join(dst, filepath),
            os.path.join(dst, os.path.basename(filepath))
        )
        os.removedirs(os.path.dirname(os.path.join(dst, filepath)))


class DirNode(object):
    """
    Class to abstract operations like list, open on directories
    """

    def __init__(self, path):
        self.path = path

    def list_files(self, directory):
        """
        List all files of current DirNode Object that are in `directory` path
        or in nested folders of directory.

        Args:
            directory (str): Directory path to limit returned files

        Returns:
            list: Names of members of ZipFile object within `directory`
        """
        full_path = os.path.join(self.path, directory)
        result = [
            os.path.join(dp, f)
            for dp, _, filenames in os.walk(full_path) for f in filenames
        ]
        return result

    def open(self, filepath):
        """
        Open the file in `filepath`.

        Args:
            filepath (str): Filename of the member of the archive to extract

        Returns:
            file object.
        """
        return open(filepath, 'r')

    def extract(self, filepath, dst):
        """
        Creates a hardlink for the file located in filepath under dst folder.

        Args:
            filepath (str): Filename of the member of the archive to extract
            dst (str): Destination folder to create the harldink.

        Returns:
        """
        if not os.path.exists(dst):
            os.makedirs(dst)
        os.link(filepath, os.path.join(dst, os.path.basename(filepath)))
