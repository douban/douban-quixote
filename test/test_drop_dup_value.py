#!/usr/bin/env python
# coding: utf-8

import unittest

from cStringIO import StringIO
from urllib import urlencode

from base import BaseTestCase

from quixote.http_request import HTTPRequest


class ParseFormTestCase(BaseTestCase):

    def test_dup_var_should_be_removed(self):
        fields_qs = [
            ('a', 1),
            ('b', 1),
        ]

        fields_form = [
            ('a', 1),
            ('b', 2),
        ]

        qs = urlencode(fields_qs)
        body = urlencode(fields_form)
        stdin = StringIO(body)

        env = {
            'SERVER_PROTOCOL': 'HTTP/1.0',
            'REQUEST_METHOD': 'POST',
            'PATH_INFO': '/',
            'CONTENT_TYPE': "application/x-www-form-urlencoded",
            'CONTENT_LENGTH': str(len(body)),
            'QUERY_STRING': qs, 
        }


        req = HTTPRequest(stdin, env)
        req.process_inputs()

        self.assertEqual(req.form, {'a': ['1', '1'], 'b': ['2', '1']})

        self.assertEqual(req.get_form_var('a'), '1')
        self.assertEqual(req.get_form_list_var('a'), ['1', '1'])

        self.assertEqual(req.get_form_var('b'), ['2','1'])
        self.assertEqual(req.get_form_list_var('b'), ['2','1'])



if __name__ == '__main__':
    unittest.main()

