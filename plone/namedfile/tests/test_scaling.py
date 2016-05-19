# -*- coding: utf-8 -*-
from datetime import datetime
from io import StringIO
from persistent import Persistent
from plone.namedfile.field import NamedImage as NamedImageField
from plone.namedfile.file import NamedImage
from plone.namedfile.interfaces import IAvailableSizes
from plone.namedfile.interfaces import IImageScaleTraversable
from plone.namedfile.scaling import ImageScaling
from plone.namedfile.testing import PLONE_NAMEDFILE_FUNCTIONAL_TESTING
from plone.namedfile.testing import PLONE_NAMEDFILE_INTEGRATION_TESTING
from plone.scale.interfaces import IScaledImageQuality
from zope.annotation import IAttributeAnnotatable
from zope.component import getGlobalSiteManager
from zope.component import getSiteManager
from zope.interface import implementer
from zope.traversing.browser.interfaces import IAbsoluteURL

import os
import PIL
import re
import time
import unittest


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
    image = PIL.Image.open(StringIO(data))
    testcase.assertEqual(image.format, format_)
    testcase.assertEqual(image.size, size)


@implementer(IAttributeAnnotatable, IHasImage)
class DummyContent(Persistent):
    image = None
    modified = datetime.now()
    id = __name__ = 'item'
    title = 'foo'

    def Title(self):
        return self.title


@implementer(IScaledImageQuality)
class DummyQualitySupplier(object):
    """ fake utility for plone.app.imaging's scaling quality """

    def getQuality(self):
        return 1  # as bad as it gets


class ImageScalingTests(unittest.TestCase):

    layer = PLONE_NAMEDFILE_INTEGRATION_TESTING

    def setUp(self):
        data = getFile('image.gif').read()
        item = DummyContent()
        item.image = NamedImage(data, 'image/gif', u'image.gif')
        self.layer['app']._setOb('item', item)
        self.item = self.layer['app'].item
        self.scaling = ImageScaling(self.item, None)

    def testCreateScale(self):
        foo = self.scaling.scale('image', width=100, height=80)
        self.assertTrue(foo.uid)
        self.assertEqual(foo.mimetype, 'image/jpeg')
        self.assertEqual(foo.width, 80)
        self.assertEqual(foo.height, 80)
        assertImage(self, foo.data.data, 'JPEG', (80, 80))

    def testCreateScaleWithoutData(self):
        item = DummyContent()
        scaling = ImageScaling(item, None)
        foo = scaling.scale('image', width=100, height=80)
        self.assertEqual(foo, None)

    def testGetScaleByName(self):
        self.scaling.available_sizes = {'foo': (60, 60)}
        foo = self.scaling.scale('image', scale='foo')
        self.assertTrue(foo.uid)
        self.assertEqual(foo.mimetype, 'image/jpeg')
        self.assertEqual(foo.width, 60)
        self.assertEqual(foo.height, 60)
        assertImage(self, foo.data.data, 'JPEG', (60, 60))
        expected_url = re.compile(
            r'http://nohost/item/@@images/[-a-z0-9]{36}\.jpeg')
        self.assertTrue(expected_url.match(foo.absolute_url()))
        self.assertEqual(foo.url, foo.absolute_url())

        tag = foo.tag()
        base = IAbsoluteURL(self.item, '')
        expected = (
            r'<img src="{0:s}/@@images/([-0-9a-f]{{36}}).(jpeg|gif|png)" '
            r'alt="foo" title="foo" height="(\d+)" width="(\d+)" />'.format(
                base))
        groups = re.match(expected, tag).groups()
        self.assertTrue(groups, tag)

    def testGetUnknownScale(self):
        foo = self.scaling.scale('image', scale='foo?')
        self.assertEqual(foo, None)

    def testScaleInvalidation(self):
        # first get the scale of the original image
        self.scaling.available_sizes = {'foo': (23, 23)}
        foo1 = self.scaling.scale('image', scale='foo')
        wait_to_ensure_modified()
        # now upload a new one and make sure the scale has changed
        data = getFile('image.jpg').read()
        self.item.image = NamedImage(data, 'image/jpeg', u'image.jpg')
        foo2 = self.scaling.scale('image', scale='foo')
        self.assertFalse(foo1.data == foo2.data, 'scale not updated?')

    def testCustomSizeChange(self):
        # set custom image sizes & view a scale
        self.scaling.available_sizes = {'foo': (23, 23)}
        foo = self.scaling.scale('image', scale='foo')
        self.assertEqual(foo.width, 23)
        self.assertEqual(foo.height, 23)
        # now let's update the scale dimensions, after which the scale
        # shouldn't be the same...
        self.scaling.available_sizes = {'foo': (42, 42)}
        foo = self.scaling.scale('image', scale='foo')
        self.assertEqual(foo.width, 42)
        self.assertEqual(foo.height, 42)

    def testAvailableSizes(self):
        # by default, no named scales are configured
        self.assertEqual(self.scaling.available_sizes, {})

        # a callable can be used to look up the available sizes
        def custom_available_sizes():
            return {'bar': (10, 10)}
        sm = getSiteManager()
        sm.registerUtility(component=custom_available_sizes,
                           provided=IAvailableSizes)
        self.assertEqual(self.scaling.available_sizes, {'bar': (10, 10)})
        sm.unregisterUtility(provided=IAvailableSizes)
        # for testing purposes, the sizes may also be set directly on
        # the scaling adapter
        self.scaling.available_sizes = {'qux': (12, 12)}
        self.assertEqual(self.scaling.available_sizes, {'qux': (12, 12)})

    def testGetAvailableSizes(self):
        self.scaling.available_sizes = {'foo': (60, 60)}
        assert self.scaling.getAvailableSizes('image') == {'foo': (60, 60)}

    def testGetImageSize(self):
        assert self.scaling.getImageSize('image') == (200, 200)

    def testGetOriginalScaleTag(self):
        tag = self.scaling.tag('image')
        base = IAbsoluteURL(self.item, '')
        expected = (
            r'<img src="{0:s}/@@images/([-0-9a-f]{{36}}).(jpeg|gif|png)" '
            r'alt="foo" title="foo" height="(\d+)" width="(\d+)" />'.format(
                base))
        self.assertTrue(re.match(expected, tag).groups())

    def testScaleOnItemWithNonASCIITitle(self):
        self.item.title = '\xc3\xbc'
        tag = self.scaling.tag('image')
        base = IAbsoluteURL(self.item, '')
        expected = (
            r'<img src="{0:s}/@@images/([-0-9a-f]{{36}}).(jpeg|gif|png)" '
            r'alt="\xfc" title="\xfc" height="(\d+)" width="(\d+)" />'.format(
                base))
        self.assertTrue(re.match(expected, tag).groups())

    def testScaleOnItemWithUnicodeTitle(self):
        self.item.Title = lambda: b'\xc3\xbc'.decode('utf8')
        tag = self.scaling.tag('image')
        base = IAbsoluteURL(self.item, '')
        expected = (
            r'<img src="{0:s}/@@images/([-0-9a-f]{{36}}).(jpeg|gif|png)" '
            r'alt="\xfc" title="\xfc" height="(\d+)" width="(\d+)" />'.format(
                base))
        self.assertTrue(re.match(expected, tag).groups())

    def testScaledImageQuality(self):
        # scale an image, record its size
        foo = self.scaling.scale('image', width=100, height=80)
        size_foo = foo.data.getSize()
        # let's pretend p.a.imaging set the scaling quality to "really sloppy"
        gsm = getGlobalSiteManager()
        qualitySupplier = DummyQualitySupplier()
        gsm.registerUtility(qualitySupplier.getQuality, IScaledImageQuality)
        wait_to_ensure_modified()
        # now scale again
        bar = self.scaling.scale('image', width=100, height=80)
        size_bar = bar.data.getSize()
        # first one should be bigger
        self.assertTrue(size_foo > size_bar)


class ImageTraverseTests(unittest.TestCase):

    layer = PLONE_NAMEDFILE_FUNCTIONAL_TESTING

    def setUp(self):
        self.app = self.layer['app']
        data = getFile('image.gif').read()
        item = DummyContent()
        item.image = NamedImage(data, 'image/gif', u'image.gif')
        self.app._setOb('item', item)
        self.item = self.app.item
        self._orig_sizes = ImageScaling._sizes

    def tearDown(self):
        ImageScaling._sizes = self._orig_sizes

    def traverse(self, path=''):
        view = self.item.unrestrictedTraverse('@@images')
        stack = path.split('/')
        name = stack.pop(0)
        static_traverser = view.traverse(name, stack)
        scale = stack.pop(0)
        tag = static_traverser.traverse(scale, stack)
        base = self.item.absolute_url()
        expected = (
            r'<img src="{0:s}/@@images/([-0-9a-f]{{36}}).(jpeg|gif|png)" '
            r'alt="foo" title="foo" height="(\d+)" width="(\d+)" />'.format(
                base))
        groups = re.match(expected, tag).groups()
        self.assertTrue(groups, tag)
        uid, ext, height, width = groups
        return uid, ext, int(width), int(height)

    def testImageThumb(self):
        ImageScaling._sizes = {'thumb': (128, 128)}
        uid, ext, width, height = self.traverse('image/thumb')
        self.assertEqual((width, height), ImageScaling._sizes['thumb'])
        self.assertEqual(ext, 'jpeg')

    def testCustomSizes(self):
        # set custom image sizes
        ImageScaling._sizes = {'foo': (23, 23)}
        # make sure traversing works with the new sizes
        uid, ext, width, height = self.traverse('image/foo')
        self.assertEqual(width, 23)
        self.assertEqual(height, 23)

    def testScaleInvalidation(self):
        # first view the thumbnail of the original image
        ImageScaling._sizes = {'thumb': (128, 128)}
        uid1, ext, width1, height1 = self.traverse('image/thumb')
        wait_to_ensure_modified()
        # now upload a new one and make sure the thumbnail has changed
        data = getFile('image.jpg').read()
        self.item.image = NamedImage(data, 'image/jpeg', u'image.jpg')
        uid2, ext, width2, height2 = self.traverse('image/thumb')
        self.assertNotEqual(uid1, uid2, 'thumb not updated?')
        # the height also differs as the original image had a size of 200, 200
        # whereas the updated one has 500, 200...
        self.assertEqual(width1, width2)
        self.assertNotEqual(height1, height2)

    def testCustomSizeChange(self):
        # set custom image sizes & view a scale
        ImageScaling._sizes = {'foo': (23, 23)}
        uid1, ext, width, height = self.traverse('image/foo')
        self.assertEqual(width, 23)
        self.assertEqual(height, 23)
        # now let's update the scale dimensions, after which the scale
        # should also have been updated...
        ImageScaling._sizes = {'foo': (42, 42)}
        uid2, ext, width, height = self.traverse('image/foo')
        self.assertEqual(width, 42)
        self.assertEqual(height, 42)
        self.assertNotEqual(uid1, uid2, 'scale not updated?')


def test_suite():
    from unittest import defaultTestLoader
    return defaultTestLoader.loadTestsFromName(__name__)
