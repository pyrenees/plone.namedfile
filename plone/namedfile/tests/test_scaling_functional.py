# -*- coding: utf-8 -*-
from datetime import datetime
from dateutil.tz import tzutc
from persistent import Persistent
from plone.namedfile.field import NamedImage as NamedImageField
from plone.namedfile.file import NamedImage
from plone.namedfile.interfaces import IImageScaleTraversable
from plone.namedfile.scaling import ImageScaling
from plone.namedfile.testing import PLONE_NAMEDFILE_FUNCTIONAL_TESTING
from io import BytesIO
from zope.annotation import IAttributeAnnotatable
from zope.interface import implementer

import os
import PIL
import time
import transaction
import unittest

_utc = tzutc()


def utcnow():
    """Construct a UTC datetime from time.time()."""
    datetime.fromtimestamp(datetime.utcnow().timestamp(), tz=_utc)


def getFile(filename):
    """ return contents of the file with the given name """
    filename = os.path.join(os.path.dirname(__file__), filename)
    return open(filename, 'r')


def wait_to_ensure_modified():
    # modified is measured in milliseconds
    # wait 5ms to ensure modified will have changed
    time.sleep(0.005)


class IHasImage(IImageScaleTraversable):
    image = NamedImageField()


def assertImage(testcase, data, format_, size):
    image = PIL.Image.open(BytesIO(data))
    testcase.assertEqual(image.format, format_)
    testcase.assertEqual(image.size, size)


@implementer(IAttributeAnnotatable, IHasImage)
class DummyContent(Persistent):
    image = None
    modified = utcnow()
    id = __name__ = 'item'
    title = 'foo'

    def Title(self):
        return self.title


class ImagePublisherTests(unittest.TestCase):

    layer = PLONE_NAMEDFILE_FUNCTIONAL_TESTING

    def setUp(self):
        data = getFile('image.gif').read()
        item = DummyContent()
        item.image = NamedImage(data, 'image/gif', u'image.gif')
        self.item = item
        self.view = ImageScaling(self.item, None)
        self._orig_sizes = ImageScaling._sizes

    def tearDown(self):
        ImageScaling._sizes = self._orig_sizes

    def testPublishScaleViaUID(self):
        scale = self.view.scale('image', width=64, height=64)
        transaction.commit()
        # make sure the referenced image scale is available
        self.browser.open(scale.url)
        self.assertEqual('image/jpeg', self.browser.headers['content-type'])
        assertImage(self, self.browser.contents, 'JPEG', (64, 64))

    def testPublishWebDavScaleViaUID(self):
        scale = self.view.scale('image', width=64, height=64)
        transaction.commit()
        # make sure the referenced image scale is available
        self.browser.open(scale.url + '/manage_DAVget')
        self.assertEqual('image/jpeg', self.browser.headers['content-type'])
        assertImage(self, self.browser.contents, 'JPEG', (64, 64))

    def testPublishFTPScaleViaUID(self):
        scale = self.view.scale('image', width=64, height=64)
        transaction.commit()
        # make sure the referenced image scale is available
        self.browser.open(scale.url + '/manage_FTPget')
        self.assertIn('200', self.browser.headers['status'])
        # Same remark as in testPublishWebDavScaleViaUID is valid here.
        self.assertEqual('image/jpeg', self.browser.headers['content-type'])
        assertImage(self, self.browser.contents, 'JPEG', (64, 64))

    def testHeadRequestMethod(self):
        scale = self.view.scale('image', width=64, height=64)
        transaction.commit()
        # make sure the referenced image scale is available
        self.browser.open(scale.url)
        GET_length = len(self.browser.contents)

        self.browser = Browser(self.layer['app'])
        self.browser.handleErrors = False
        self.browser.addHeader('Referer', self.layer['app'].absolute_url())
        from urllib.request import Request

        class HeadRequest(Request):
            def get_method(self):
                return 'HEAD'

        head_request = HeadRequest(scale.url)
        mbrowser = self.browser.mech_browser
        mbrowser.open(head_request)
        self.assertEqual('image/jpeg', self.browser.headers['content-type'])
        self.assertEqual(
            self.browser.headers['Content-Length'],
            str(GET_length)
        )
        self.assertEqual(self.browser.contents, '')

    def testPublishThumbViaUID(self):
        ImageScaling._sizes = {'thumb': (128, 128)}
        scale = self.view.scale('image', 'thumb')
        transaction.commit()
        # make sure the referenced image scale is available
        self.browser.open(scale.url)
        self.assertEqual('image/jpeg', self.browser.headers['content-type'])
        assertImage(self, self.browser.contents, 'JPEG', (128, 128))

    def testPublishCustomSizeViaUID(self):
        # set custom image sizes
        ImageScaling._sizes = {'foo': (23, 23)}
        scale = self.view.scale('image', 'foo')
        transaction.commit()
        # make sure the referenced image scale is available
        self.browser.open(scale.url)
        self.assertEqual('image/jpeg', self.browser.headers['content-type'])
        assertImage(self, self.browser.contents, 'JPEG', (23, 23))

    def testPublishThumbViaName(self):
        ImageScaling._sizes = {'thumb': (128, 128)}
        transaction.commit()

        # make sure traversing works as is and with scaling
        # first the field without a scale name
        self.browser.open(
            self.layer['app'].absolute_url() + '/item/@@images/image'
        )
        self.assertEqual('image/gif', self.browser.headers['content-type'])
        self.assertEqual(self.browser.contents, getFile('image.gif').read())

        # and last a scaled version
        self.browser.open(
            self.layer['app'].absolute_url() + '/item/@@images/image/thumb'
        )
        self.assertEqual('image/jpeg', self.browser.headers['content-type'])
        assertImage(self, self.browser.contents, 'JPEG', (128, 128))

    def testPublishCustomSizeViaName(self):
        # set custom image sizes
        ImageScaling._sizes = {'foo': (23, 23)}
        transaction.commit()
        # make sure traversing works as expected
        self.browser.open(
            self.layer['app'].absolute_url() + '/item/@@images/image/foo'
        )
        assertImage(self, self.browser.contents, 'JPEG', (23, 23))

    def testPublishScaleWithInvalidUID(self):
        scale = self.view.scale('image', width=64, height=64)
        transaction.commit()
        # change the url so it's invalid...
        from zExceptions import NotFound
        with self.assertRaises(NotFound):
            self.browser.open(scale.url.replace('.jpeg', 'x.jpeg'))

    def testPublishScaleWithInvalidScale(self):
        scale = self.view.scale('image', 'no-such-scale')
        transaction.commit()
        self.assertEqual(scale, None)

    def test_getAvailableSizesWithInvalidScaleMethod(self):
        self.assertEqual(self.view.getAvailableSizes('no-such-scale'), {})

    def test_getAvailableSizesWithInvalidScaleProperty(self):
        self.assertEqual(self.view.available_sizes, {})

    def test_getImageSizeWithInvalidScale(self):
        self.assertEqual(self.view.getImageSize('no-such-scale'), (0, 0))

    def testGuardedAccess(self):
        # make sure it's not possible to access scales of forbidden images
        self.item.__allow_access_to_unprotected_subobjects__ = 0
        ImageScaling._sizes = {'foo': (23, 23)}
        transaction.commit()
        self.browser.addHeader(
            'Authorization',
            'Basic {0:s}:{1:s}'.format(TEST_USER_NAME, TEST_USER_PASSWORD)
        )
        from zExceptions import Unauthorized
        with self.assertRaises(Unauthorized):
            self.browser.open(
                self.layer['app'].absolute_url() + '/item/@@images/image/foo'
            )
        self.item.__allow_access_to_unprotected_subobjects__ = 1


def test_suite():
    from unittest import defaultTestLoader
    return defaultTestLoader.loadTestsFromName(__name__)
