#!/usr/bin/env python

"""
twist -- Demo of an HTTP server built on top of Twisted Python.
"""

__revision__ = "$Id$"

# based on qserv, created 2002/03/19, AMK
# last mod 2003.03.24, Graham Fawcett
# tested on Win32 / Twisted 0.18.0 / Quixote 0.6b5
#
# version 0.2 -- 2003.03.24 11:07 PM
#   adds missing support for session management, and for
#   standard Quixote response headers (expires, date)
#
# modified 2004/04/10 jsibre
#   better support for Streams
#   wraps output (whether Stream or not) into twisted type producer.
#   modified to use reactor instead of Application (Appication
#     has been deprecated)

import urllib
from twisted.protocols import http
from twisted.web import server

# imports for the TWProducer object
from twisted.spread import pb
from twisted.python import threadable
from twisted.internet import abstract

from quixote.http_response import Stream

class QuixoteTWRequest(server.Request):

    def process(self):
        self.publisher = self.channel.factory.publisher
        environ = self.create_environment()
        # this seek is important, it doesn't work without it (it doesn't
        # matter for GETs, but POSTs will not work properly without it.)
        self.content.seek(0, 0)
        qxrequest = self.publisher.create_request(self.content, environ)
        self.quixote_publish(qxrequest, environ)
        resp = qxrequest.response
        self.setResponseCode(resp.status_code)
        for hdr, value in resp.generate_headers():
            self.setHeader(hdr, value)
        if resp.body is not None:
            TWProducer(resp.body, self)
        else:
            self.finish()


    def quixote_publish(self, qxrequest, env):
        """
        Warning, this sidesteps the Publisher.publish method,
        Hope you didn't override it...
        """
        pub = self.publisher
        output = pub.process_request(qxrequest, env)

        # don't write out the output, just set the response body
        # the calling method will do the rest.
        if output:
            qxrequest.response.set_body(output)

        pub._clear_request()


    def create_environment(self):
        """
        Borrowed heavily from twisted.web.twcgi
        """
        # Twisted doesn't decode the path for us,
        # so let's do it here.  This is also
        # what medusa_http.py does, right or wrong.
        if '%' in self.path:
            self.path = urllib.unquote(self.path)

        serverName = self.getRequestHostname().split(':')[0]
        env = {"SERVER_SOFTWARE":   server.version,
               "SERVER_NAME":       serverName,
               "GATEWAY_INTERFACE": "CGI/1.1",
               "SERVER_PROTOCOL":   self.clientproto,
               "SERVER_PORT":       str(self.getHost()[2]),
               "REQUEST_METHOD":    self.method,
               "SCRIPT_NAME":       '',
               "SCRIPT_FILENAME":   '',
               "REQUEST_URI":       self.uri,
               "HTTPS":             (self.isSecure() and 'on') or 'off',
               "ACCEPT_ENCODING":   self.getHeader('Accept-encoding'),
               'CONTENT_TYPE':      self.getHeader('Content-type'),
               'HTTP_COOKIE':       self.getHeader('Cookie'),
               'HTTP_REFERER':      self.getHeader('Referer'),
               'HTTP_USER_AGENT':   self.getHeader('User-agent'),
               'SERVER_PROTOCOL':   'HTTP/1.1',
        }

        client = self.getClient()
        if client is not None:
            env['REMOTE_HOST'] = client
        ip = self.getClientIP()
        if ip is not None:
            env['REMOTE_ADDR'] = ip
        xx, xx, remote_port = self.transport.getPeer()
        env['REMOTE_PORT'] = remote_port
        env["PATH_INFO"] = self.path

        qindex = self.uri.find('?')
        if qindex != -1:
            env['QUERY_STRING'] = self.uri[qindex+1:]
        else:
            env['QUERY_STRING'] = ''

        # Propogate HTTP headers
        for title, header in self.getAllHeaders().items():
            envname = title.replace('-', '_').upper()
            if title not in ('content-type', 'content-length'):
                envname = "HTTP_" + envname
            env[envname] = header

        return env


class TWProducer(pb.Viewable):
    """
    A class to represent the transfer of data over the network.

    JES Note: This has more stuff in it than is minimally neccesary.
    However, since I'm no twisted guru, I built this by modifing
    twisted.web.static.FileTransfer.  FileTransfer has stuff in it
    that I don't really understand, but know that I probably don't
    need. I'm leaving it in under the theory that if anyone ever
    needs that stuff (e.g. because they're running with multiple
    threads) it'll be MUCH easier for them if I had just left it in
    than if they have to figure out what needs to be in there.
    Furthermore, I notice no performance penalty for leaving it in.
    """
    request = None
    def __init__(self, data, request):
        self.request = request
        self.data = ""
        self.size = 0
        self.stream = None
        self.streamIter = None

        self.outputBufferSize = abstract.FileDescriptor.bufferSize

        if isinstance(data, Stream):    # data could be a Stream
            self.stream = data
            self.streamIter = iter(data)
            self.size = data.length
        elif data:                      # data could be a string
            self.data = data
            self.size = len(data)
        else:                           # data could be None
            # We'll just leave self.data as ""
            pass

        request.registerProducer(self, 0)


    def resumeProducing(self):
        """
        This is twisted's version of a producer's '.more()', or
        an iterator's '.next()'.  That is, this function is
        responsible for returning some content.
        """
        if not self.request:
            return

        if self.stream:
            # If we were provided a Stream, let's grab some data
            # and push it into our data buffer

            buffer = [self.data]
            bytesInBuffer = len(buffer[-1])
            while bytesInBuffer < self.outputBufferSize:
                try:
                    buffer.append(self.streamIter.next())
                    bytesInBuffer += len(buffer[-1])
                except StopIteration:
                    # We've exhausted the Stream, time to clean up.
                    self.stream = None
                    self.streamIter = None
                    break
            self.data = "".join(buffer)

        if self.data:
            chunkSize = min(self.outputBufferSize, len(self.data))
            data, self.data = self.data[:chunkSize], self.data[chunkSize:]
        else:
            data = ""

        if data:
            self.request.write(data)

        if not self.data:
            self.request.unregisterProducer()
            self.request.finish()
            self.request = None

    def pauseProducing(self):
        pass

    def stopProducing(self):
        self.data    = ""
        self.request = None
        self.stream  = None
        self.streamIter = None

    # Remotely relay producer interface.

    def view_resumeProducing(self, issuer):
        self.resumeProducing()

    def view_pauseProducing(self, issuer):
        self.pauseProducing()

    def view_stopProducing(self, issuer):
        self.stopProducing()

    synchronized = ['resumeProducing', 'stopProducing']

threadable.synchronize(TWProducer)



class QuixoteFactory(http.HTTPFactory):

    def __init__(self, publisher):
        self.publisher = publisher
        http.HTTPFactory.__init__(self, None)

    def buildProtocol(self, addr):
        p = http.HTTPFactory.buildProtocol(self, addr)
        p.requestFactory = QuixoteTWRequest
        return p


def Server(namespace, http_port):
    from twisted.internet import reactor
    from quixote.publish import Publisher

    #  If you want SSL, make sure you have OpenSSL,
    #  uncomment the follownig, and uncomment the
    #  listenSSL() call below.

    ##from OpenSSL import SSL
    ##class ServerContextFactory:
    ##    def getContext(self):
    ##        ctx = SSL.Context(SSL.SSLv23_METHOD)
    ##        ctx.use_certificate_file('/path/to/pem/encoded/ssl_cert_file')
    ##        ctx.use_privatekey_file('/path/to/pem/encoded/ssl_key_file')
    ##        return ctx

    publisher = Publisher(namespace)
    ##publisher.setup_logs()
    qf = QuixoteFactory(publisher)

    reactor.listenTCP(http_port, qf)
    ##reactor.listenSSL(http_port, qf, ServerContextFactory())

    return reactor


def run(namespace, port):
    app = Server(namespace, port)
    app.run()


if __name__ == '__main__':
    from quixote import enable_ptl
    enable_ptl()
    run('quixote.demo', 8080)
