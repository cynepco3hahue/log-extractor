"""
Tests for LZMAFile class
"""
import lzma
from StringIO import StringIO
from log_extractor.files import LZMAFile

TEXT = """Hello this is my nice testing text
which has many lines
containing various bullshit ...
"""
TEXT_BY_LINE = TEXT.splitlines()


def test_easy():
    file_obj = StringIO(lzma.compress(TEXT))
    xzfile = LZMAFile(file_obj)
    linecount = 0
    for line in xzfile:
        assert(line == TEXT_BY_LINE[linecount])
        linecount += 1


def test_small_buffer():
    file_obj = StringIO(lzma.compress(TEXT))
    xzfile = LZMAFile(file_obj, buff_size=16)
    linecount = 0
    for line in xzfile:
        assert(line == TEXT_BY_LINE[linecount])
        linecount += 1
