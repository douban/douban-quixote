#!/usr/bin/env python
# coding: utf-8

import sys
import os
import os.path
import unittest
import shutil

from webtest import TestApp
from webtest import Upload

from base import BaseTestCase

from quixote.qwip import QWIP
from quixote.publish import Publisher


upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'upload')
if not os.path.exists(upload_dir):
    os.mkdir(upload_dir)
for name in os.listdir(upload_dir):
    path = os.path.join(upload_dir, name)
    try:
        os.remove(path)
    except OSError:
        shutil.rmtree(path, ignore_errors=True)


class UITest(object):
    _q_exports = ['upload', 'form']

    def form(self, req):
        return '<html><head></head><body><form method="POST" action="/upload" enctype="multipart/form-data" ><input name="file" type="file"/></form></body></html>'

    def upload(self, req):
        if req.get_method() == 'POST':
            upload = req.get_form_var("file")
            fname = upload.orig_filename
            data = open(upload.tmp_filename).read()
            return '%s %s' % (fname, data)


class QWIPTestCase(BaseTestCase):
    def setUp(self):
        conf = dict(UPLOAD_DIR=upload_dir)
        self.app = TestApp(QWIP(self.create_publisher(UITest, conf)))

    def test_form(self):
        res = self.app.get('/form')
        form = res.form
        fname = 'test.txt'
        data = 'test'*10
        form['file'] = Upload(fname, data)
        resp = form.submit(content_type="multipart/form-data")
        assert resp.body == '%s %s' % (fname, data)
        assert len(os.listdir(upload_dir)) == 0


if __name__ == '__main__':
    unittest.main()
