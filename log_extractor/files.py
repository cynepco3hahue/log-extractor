import os
import zipfile
import tarfile
import lzma


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
        if filepath.endswith(".xz"):
            return LZMAFile(self.tf.extractfile(filepath))
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


class LZMAFile(object):
    """
    Class to abstract operations on .bz files
    """

    def __init__(self, file_obj, buff_size=4096):
        self.f = file_obj
        self.d = lzma.LZMADecompressor()
        self.buff = ""
        self.buff_size = buff_size

    def __enter__(self):
        return self

    def __iter__(self):
        return self

    def __exit__(self, type_, value, tb):
        self.close()

    def __next__(self):
        """
        Manually iterate through all the items of an LZMAFile iterator.
        Will allow us to read LZMA files line by line in for loop like,
        for line in lzma_file:
        """
        if self.buff:
            maybe_line = self.buff.split("\n", 1)
            if len(maybe_line) > 1:
                line, self.buff = maybe_line
                return line
        buff = ""
        while True:
            if not buff:
                buff = self.f.read(self.buff_size)
                if not buff:
                    if self.buff:
                        buff = self.buff
                        self.buff = ""
                        return buff
                    raise StopIteration()
                self.buff += self.d.decompress(buff)

            maybe_line = self.buff.split("\n", 1)
            if len(maybe_line) == 1:
                buff = ""
                continue
            line, self.buff = maybe_line
            return line
    next = __next__

    def close(self):
        self.f.close()


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
