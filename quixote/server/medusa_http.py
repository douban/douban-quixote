#!/usr/bin/env python

"""quixote.server.medusa_http

An HTTP handler for Medusa that publishes a Quixote application.
"""

__revision__ = "$Id$"

# A simple HTTP server, using Medusa, that publishes a Quixote application.

import sys
import asyncore, rfc822, socket, urllib
from StringIO import StringIO
from medusa import http_server, xmlrpc_handler
from quixote.http_response import Stream
from quixote.publish import Publisher


class StreamProducer:
    def __init__(self, stream):
        self.iterator = iter(stream)

    def more(self):
        try:
            return self.iterator.next()
        except StopIteration:
            return ''


class QuixoteHandler:
    def __init__(self, publisher, server_name, server):
        """QuixoteHandler(publisher:Publisher, server_name:string,
                        server:medusa.http_server.http_server)

        Publish the specified Quixote publisher.  'server_name' will
        be passed as the SERVER_NAME environment variable.
        """
        self.publisher = publisher
        self.server_name = server_name
        self.server = server

    def match(self, request):
        # Always match, since this is the only handler there is.
        return 1

    def handle_request(self, request):
        msg = rfc822.Message(StringIO('\n'.join(request.header)))
        length = int(msg.get('Content-Length', '0'))
        if length:
            request.collector = xmlrpc_handler.collector(self, request)
        else:
            self.continue_request('', request)

    def continue_request(self, data, request):
        msg = rfc822.Message(StringIO('\n'.join(request.header)))
        remote_addr, remote_port = request.channel.addr
        if '#' in request.uri:
            # MSIE is buggy and sometimes includes fragments in URLs
            [request.uri, fragment] = request.uri.split('#', 1)
        if '?' in request.uri:
            [path, query_string] = request.uri.split('?', 1)
        else:
            path = request.uri
            query_string = ''

        path = urllib.unquote(path)
        server_port = str(self.server.port)
        http_host = msg.get("Host")
        if http_host:
            if ":" in http_host:
                server_name, server_port = http_host.split(":", 1)
            else:
                server_name = http_host
        else:
            server_name = (self.server.ip or
                           socket.gethostbyaddr(socket.gethostname())[0])

        environ = {'REQUEST_METHOD': request.command,
                   'ACCEPT_ENCODING': msg.get('Accept-encoding', ''),
                   'CONTENT_TYPE': msg.get('Content-type', ''),
                   'CONTENT_LENGTH': len(data),
                   "GATEWAY_INTERFACE": "CGI/1.1",
                   'PATH_INFO': path,
                   'QUERY_STRING': query_string,
                   'REMOTE_ADDR': remote_addr,
                   'REMOTE_PORT': str(remote_port),
                   'REQUEST_URI': request.uri,
                   'SCRIPT_NAME': '',
                   "SCRIPT_FILENAME": '',
                   'SERVER_NAME': server_name,
                   'SERVER_PORT': server_port,
                   'SERVER_PROTOCOL': 'HTTP/1.1',
                   'SERVER_SOFTWARE': self.server_name,
                   }
        for title, header in msg.items():
            envname = 'HTTP_' + title.replace('-', '_').upper()
            environ[envname] = header

        stdin = StringIO(data)
        qreq = self.publisher.create_request(stdin, environ)
        output = self.publisher.process_request(qreq, environ)

        qresponse = qreq.response
        if output:
            qresponse.set_body(output)

        # Copy headers from Quixote's HTTP response
        for name, value in qresponse.generate_headers():
            # XXX Medusa's HTTP request is buggy, and only allows unique
            # headers.
            request[name] = value

        request.response(qresponse.status_code)

        # XXX should we set a default Last-Modified time?
        if qresponse.body is not None:
            if isinstance(qresponse.body, Stream):
                request.push(StreamProducer(qresponse.body))
            else:
                request.push(qresponse.body)

        request.done()

def main():
    from quixote import enable_ptl
    enable_ptl()

    if len(sys.argv) == 2:
        port = int(sys.argv[1])
    else:
        port = 8080
    print 'Now serving the Quixote demo on port %d' % port
    server = http_server.http_server('', port)
    publisher = Publisher('quixote.demo')

    # When initializing the Publisher in your own driver script,
    # you'll want to parse a configuration file.
    ##publisher.read_config("/full/path/to/demo.conf")
    publisher.setup_logs()
    dh = QuixoteHandler(publisher, 'Quixote/demo', server)
    server.install_handler(dh)
    asyncore.loop()

if __name__ == '__main__':
    main()
