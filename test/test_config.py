from unittest import TestCase
from quixote.publish import Publisher
from quixote.http_request import HTTPJSONRequest
from cStringIO import StringIO

class TestConfig(TestCase):
    def test_config_for_application_json_support(self):
        pub = Publisher('__main__')
        self.assertFalse(pub.config.support_application_json)

        req = pub.create_request(StringIO(), {'CONTENT_TYPE': "application/json"})
        self.assertFalse(isinstance(req, HTTPJSONRequest))

        pub.configure(SUPPORT_APPLICATION_JSON=1)

        req = pub.create_request(StringIO(), {'CONTENT_TYPE': "application/json"})
        self.assertTrue(isinstance(req, HTTPJSONRequest))
