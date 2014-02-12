# -*- coding:utf8 -*-
from unittest import TestCase
from quixote.errors import QueryError
from quixote.http_request import HTTPJSONRequest
from cStringIO import StringIO
from json import loads, dumps

class TestJSONRequest(TestCase):
    def setUp(self):
        self.fake_environ = {'CONTENT_LENGTH': '291',
                             'CONTENT_TYPE': 'application/json; charset=utf-8'}

    def test_process_input_of_json_object(self):
        json = dumps({
            "1": u"哈哈哈",
            u"a": {
                "b": {
                    "二": u"我",
                },
            },
            "c": [u"我", u"你", u"c"],
        }, ensure_ascii=True)

        req = HTTPJSONRequest(StringIO(json), self.fake_environ)
        req.process_inputs()
        self.assertEqual(req.json, {
            "1": "哈哈哈",
            "a": {
                "b": {
                    "二": "我",
                },
            },
            "c": ["我", "你", "c"],
        })
        self.assertEqual(req.json, req.form)

    def test_process_input_of_json_array(self):
        json = dumps([
            u"哈哈哈",
            u"a",
            u"我",
            u"你",
            u"c",
        ], ensure_ascii=True)

        req = HTTPJSONRequest(StringIO(json), self.fake_environ)
        req.process_inputs()
        self.assertEqual(req.json, [
            "哈哈哈",
            "a",
            "我",
            "你",
            "c",
        ])

    def test_query_error(self):
        req = HTTPJSONRequest(StringIO(''), self.fake_environ)
        self.assertRaises(QueryError, req.process_inputs)
