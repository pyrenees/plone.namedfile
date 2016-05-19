# -*- coding: utf-8 -*-
# This file was borrowed from z3c.blobfile and is licensed under the terms of
# the ZPL.
from io import IOBase
from plone.namedfile.file import FileChunk
from plone.namedfile.interfaces import IStorage
from plone.namedfile.interfaces import NotStorable
from zope.interface import implementer
from zope.publisher.browser import FileUpload


MAXCHUNKSIZE = 1 << 16


@implementer(IStorage)
class BytesStorable(object):

    def store(self, data, blob):
        if not isinstance(data, bytes):
            raise NotStorable('Could not store data (not of "bytes" type).')

        with blob.open('w') as fp:
            fp.write(data)


@implementer(IStorage)
class StringStorable(BytesStorable):

    def store(self, data, blob):
        if not isinstance(data, str):
            raise NotStorable('Could not store data (not of "str" type).')

        data = data.encode('UTF-8')
        StringStorable.store(self, data, blob)


@implementer(IStorage)
class FileChunkStorable(object):

    def store(self, data, blob):
        if not isinstance(data, FileChunk):
            raise NotStorable('Could not store data (not a of "FileChunk" type).')  # noqa

        with blob.open('w') as fp:
            chunk = data
            while chunk:
                fp.write(chunk._data)
                chunk = chunk.next


@implementer(IStorage)
class FileDescriptorStorable(object):

    def store(self, data, blob):
        if not isinstance(data, IOBase):
            raise NotStorable('Could not store data (not of "file").')

        filename = getattr(data, 'name', None)
        if filename is not None:
            blob.consumeFile(filename)
            return


@implementer(IStorage)
class FileUploadStorable(object):

    def store(self, data, blob):
        if not isinstance(data, FileUpload):
            raise NotStorable('Could not store data (not of "FileUpload").')

        data.seek(0)

        with blob.open('w') as fp:
            block = data.read(MAXCHUNKSIZE)
            while block:
                fp.write(block)
                block = data.read(MAXCHUNKSIZE)
