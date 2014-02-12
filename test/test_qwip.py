#!/usr/bin/env python
# coding: utf-8

import unittest

from webtest import TestApp
from webtest import Upload

from base import BaseTestCase

from quixote.qwip import QWIP
from quixote.publish import Publisher


class UITest(object):
    _q_exports = ['', 'upload', 'form']

    def _q_index(self, req):
        return "hello, world"

    def form(self, req):
        return '<html><head></head><body><form method="POST" action="/upload" enctype="multipart/form-data" ><input name="file" type="file"/></form></body></html>'

    def upload(self, req):
        if req.get_method() == 'POST':
            upload = req.get_form_var("file")
            return open(upload.tmp_filename).read()


class QWIPTestCase(BaseTestCase):

    def setUp(self):
        conf = dict(UPLOAD_DIR='/tmp/')
        self.app = TestApp(QWIP(self.create_publisher(UITest, conf)))

    def test_basic_page(self):
        resp = self.app.get('/')
        assert resp.status == '200 OK'
        assert resp.content_type == 'text/html'
        assert resp.body == "hello, world"

    def test_form(self):
        res = self.app.get('/form')
        form = res.form
        data = 'test'*10
        form['file'] = Upload('test.txt', data)
        resp = form.submit(content_type="multipart/form-data")
        assert resp.body == data

if __name__ == '__main__':
    unittest.main()
