# -*- coding: utf-8 -*-
from plone.testing import Layer
from plone.testing import publisher
from plone.testing import zca
from plone.testing import zodb
from zope.configuration import xmlconfig

import transaction


class NamedFileTestLayer(Layer):

    defaultBases = (publisher.PUBLISHER_DIRECTIVES,)

    def setUp(self):
        zca.pushGlobalRegistry()

        import plone.namedfile
        xmlconfig.file('testing.zcml', plone.namedfile)  # noqa

        self['zodbDB'] = zodb.stackDemoStorage(
            self.get('zodbDB'),
            name='NamedFileFixture'
        )

    def tearDown(self):
        # Zap the stacked ZODB
        self['zodbDB'].close()
        del self['zodbDB']

        # Zap the stacked zca context
        zca.popGlobalRegistry()

PLONE_NAMEDFILE_FIXTURE = NamedFileTestLayer()
PLONE_NAMEDFILE_INTEGRATION_TESTING = PLONE_NAMEDFILE_FIXTURE


class NamedFileFunctionalTestLayer(Layer):
    defaultBases = (PLONE_NAMEDFILE_FIXTURE,)

    def testSetUp(self):
        # Setup a transient db
        self['zodbDB'] = zodb.stackDemoStorage(
            self.get('zodbDB'),
            name='FunctionalTest'
        )

        # Start a transaction
        transaction.begin()

    def testTearDown(self):
        # Abort any open transactions
        transaction.abort()

        # Close and discard the database
        self['zodbDB'].close()
        del self['zodbDB']

PLONE_NAMEDFILE_FUNCTIONAL_TESTING = NamedFileFunctionalTestLayer()
