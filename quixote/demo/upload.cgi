#!/www/python/bin/python

# Simple demo of HTTP upload with Quixote.  Also serves as an example
# of how to put a (simple) Quixote application into a single file.

__revision__ = "$Id: upload.cgi 21182 2003-03-17 21:46:52Z gward $"

import os
import stat
from quixote import Publisher
from quixote.html import html_quote

_q_exports = ['receive']

def header (title):
    return '''\
      <html><head><title>%s</title></head>
      <body>
      ''' % title

def footer ():
    return '</body></html>\n'

def _q_index (request):
    return header("Quixote Upload Demo") + '''\
      <form enctype="multipart/form-data"
            method="POST" 
            action="receive">
        Your name:<br>
        <input type="text" name="name"><br>
        File to upload:<br>
        <input type="file" name="upload"><br>
        <input type="submit" value="Upload">
      </form>
      ''' + footer()

def receive (request):
    result = []
    name = request.form.get("name")
    if name:
        result.append("<p>Thanks, %s!</p>" % html_quote(name))

    upload = request.form.get("upload")
    size = os.stat(upload.tmp_filename)[stat.ST_SIZE]
    if not upload.base_filename or size == 0:
        title = "Empty Upload"
        result.append("<p>You appear not to have uploaded anything.</p>")
    else:
        title = "Upload Received"
        result.append("<p>You just uploaded <code>%s</code> (%d bytes)<br>"
                      % (html_quote(upload.base_filename), size))
        result.append("which is temporarily stored in <code>%s</code>.</p>"
                      % html_quote(upload.tmp_filename))

    return header(title) + "\n".join(result) + footer()

def main ():
    pub = Publisher('__main__')
    pub.read_config("demo.conf")
    pub.configure(UPLOAD_DIR="/tmp/quixote-upload-demo")
    pub.setup_logs()
    pub.publish_cgi()

main()
