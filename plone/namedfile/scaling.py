# -*- coding: utf-8 -*-
from datetime import datetime
from dateutil.tz import tzlocal
from plone.namedfile.file import FILECHUNK_CLASSES
from plone.namedfile.interfaces import IAvailableSizes
from plone.namedfile.interfaces import IStableImageScale
from plone.rfc822.interfaces import IPrimaryFieldInfo
from plone.scale.interfaces import IImageScaleFactory
from plone.scale.interfaces import IScaledImageQuality
from plone.scale.scale import scaleImage
from plone.scale.storage import AnnotationStorage
from xml.sax.saxutils import quoteattr
from ZODB.POSException import ConflictError
from zope.component import queryUtility
from zope.interface import alsoProvides
from zope.interface import implementer
from zope.publisher.interfaces import NotFound

import logging


logger = logging.getLogger(__name__)
_marker = object()
_zone = tzlocal()


class ImageScale(object):
    def __init__(self, context, request, **info):
        self.context = context
        self.request = request
        self.__dict__.update(**info)
        if self.data is None:
            self.data = getattr(self.context, self.fieldname)

        url = self.context.absolute_url()
        extension = self.data.contentType.split('/')[-1].lower()
        if 'uid' in info:
            name = info['uid']
        else:
            name = info['fieldname']
        self.__name__ = u'{0}.{1}'.format(name, extension)
        self.url = u'{0}/@@images/{1}'.format(url, self.__name__)

    def absolute_url(self):
        return self.url

    def tag(self, height=_marker, width=_marker, alt=_marker,
            css_class=None, title=_marker, **kwargs):
        """Create a tag including scale
        """
        if height is _marker:
            height = getattr(self, 'height', self.data._height)
        if width is _marker:
            width = getattr(self, 'width', self.data._width)

        if alt is _marker:
            alt = self.context.Title()
        if title is _marker:
            title = self.context.Title()

        values = [
            ('src', self.url),
            ('alt', alt),
            ('title', title),
            ('height', height),
            ('width', width),
            ('class', css_class),
        ]
        values.extend(kwargs.items())

        parts = ['<img']
        for k, v in values:
            if v is None:
                continue
            if isinstance(v, int):
                v = str(v)
            elif isinstance(v, bytes):
                v = v.decode('utf-8')
            parts.append(u'{0}={1}'.format(k, quoteattr(v)))
        parts.append('/>')

        return u' '.join(parts)


@implementer(IImageScaleFactory)
class DefaultImageScalingFactory(object):

    def __init__(self, context):
        self.context = context

    def get_quality(self):
        """Get plone.app.imaging's quality setting"""
        getScaledImageQuality = queryUtility(IScaledImageQuality)
        if getScaledImageQuality is None:
            return None
        return getScaledImageQuality()

    def create_scale(self, data, direction, height, width, **parameters):
        return scaleImage(
            data,
            direction=direction,
            height=height,
            width=width,
            **parameters
        )

    def __call__(  # noqa
        self,
        fieldname=None,
        direction='thumbnail',
        height=None,
        width=None,
        scale=None,
        **parameters
    ):

        """Factory for image scales`.
        """
        orig_value = getattr(self.context, fieldname)
        if orig_value is None:
            return

        if height is None and width is None:
            dummy, format_ = orig_value.contentType.split('/', 1)
            return None, format_, (orig_value._width, orig_value._height)
        try:
            orig_data = orig_value.open()
        except AttributeError:
            orig_data = getattr(orig_value, 'data', orig_value)
        if not orig_data:
            return

        # Handle cases where large image data is stored in FileChunks instead
        # of plain string
        if isinstance(orig_data, tuple(FILECHUNK_CLASSES)):
            # Convert data to 8-bit string
            # (FileChunk does not provide read() access)
            orig_data = str(orig_data)

        # If quality wasn't in the parameters, try the site's default scaling
        # quality if it exists.
        if 'quality' not in parameters:
            quality = self.get_quality()
            if quality:
                parameters['quality'] = quality

        try:
            result = self.create_scale(
                orig_data,
                direction=direction,
                height=height,
                width=width,
                **parameters
            )
        except (ConflictError, KeyboardInterrupt):
            raise
        except Exception:
            logger.exception(
                'Could not scale "{0!r:s}" of {1!r:s}'.format(
                    orig_value, self.context.absolute_url()))
            return
        if result is None:
            return

        data, format_, dimensions = result
        mimetype = u'image/{0}'.format(format_.lower())
        value = orig_value.__class__(
            data,
            contentType=mimetype,
            filename=orig_value.filename
        )
        value.fieldname = fieldname
        return value, format_, dimensions


class ImageScaling(object):
    """ view used for generating (and storing) image scales """

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def publishTraverse(self, request, name):
        """ used for traversal via publisher, i.e. when using as a url """
        if '-' in name:
            # we got a uid...
            if '.' in name:
                name, ext = name.rsplit('.', 1)
            storage = AnnotationStorage(self.context)
            info = storage.get(name)
            if info is None:
                raise NotFound(self, name, self.request)
            scale_view = ImageScale(self.context, self.request, **info)
            alsoProvides(scale_view, IStableImageScale)
            return scale_view
        else:
            # otherwise `name` must refer to a field...
            if '.' in name:
                name, ext = name.rsplit('.', 1)
            value = getattr(self.context, name)
            scale_view = ImageScale(
                self.context,
                self.request,
                data=value,
                fieldname=name
            )
            return scale_view

    _sizes = {}

    @property
    def available_sizes(self):
        # fieldname is ignored by default
        sizes_util = queryUtility(IAvailableSizes)
        if sizes_util is None:
            return self._sizes
        sizes = sizes_util()
        if sizes is None:
            return {}
        return sizes

    @available_sizes.setter
    def available_sizes(self, value):
        self._sizes = value

    def getImageSize(self, fieldname=None):
        if fieldname is not None:
            value = getattr(self.context, fieldname, None)
            if value is None:
                return (0, 0)
            return value.getImageSize()
        value = IPrimaryFieldInfo(self.context).value
        return value.getImageSize()

    def modified(self):
        """Provide a callable to return the modification time of content
        items, so stored image scales can be invalidated.
        """
        context = self.context
        date = datetime.fromtimestamp(context._p_mtime, tz=_zone)
        return date.time()

    def scale(
        self,
        fieldname=None,
        scale=None,
        height=None,
        width=None,
        direction='thumbnail',
        **parameters
    ):
        if fieldname is None:
            primary_field = IPrimaryFieldInfo(self.context, None)
            if primary_field is None:
                return  # 404
            fieldname = primary_field.fieldname
        if scale is not None:
            if width is not None or height is not None:
                logger.warn(
                    'A scale name and width/heigth are given. Those are'
                    'mutually exclusive: solved by ignoring width/heigth and '
                    'taking name'
                )
            available = self.available_sizes
            if scale not in available:
                return None  # 404
            width, height = available[scale]
        storage = AnnotationStorage(self.context, self.modified)
        info = storage.scale(
            fieldname=fieldname,
            height=height,
            width=width,
            direction=direction,
            scale=scale,
            **parameters
        )
        if info is None:
            return  # 404
        info['fieldname'] = fieldname
        scale_view = ImageScale(self.context, self.request, **info)
        return scale_view

    def tag(
        self,
        fieldname=None,
        scale=None,
        height=None,
        width=None,
        direction='thumbnail',
        **kwargs
    ):
        scale = self.scale(fieldname, scale, height, width, direction)
        return scale.tag(**kwargs) if scale else None
