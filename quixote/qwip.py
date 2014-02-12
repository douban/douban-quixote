#!/usr/bin/python
#-*-coding=utf8-*-

'''
QWIP: WSGI COMPATIBILITY WRAPPER FOR QUIXOTE
'''

from quixote.publish import set_publisher

class QWIP(object):
    """I make a Quixote Publisher object look like a WSGI application."""

    def __init__(self, publisher):
        self.publisher = publisher

    def __call__(self, env, start_response):
        """I am called for each request."""
        # maybe more than one publisher per app, need to set publisher per request
        set_publisher(self.publisher)
        if env.get('wsgi.multithread') and not \
            getattr(self.publisher, 'is_thread_safe', False):
            reason =  "%r is not thread safe" % self.publisher
            raise AssertionError(reason)
        if 'REQUEST_URI' not in env:
            env['REQUEST_URI'] = env['SCRIPT_NAME'] + env['PATH_INFO']
            if env.get('QUERY_STRING', ''):
                env['REQUEST_URI'] += '?%s' %env['QUERY_STRING']
        if env['wsgi.url_scheme'] == 'https':
            env['HTTPS'] = 'on'
        input = env['wsgi.input']
        request = self.publisher.create_request(input, env)
        output = self.publisher.process_request(request, env)
        request.response.set_body(output)
        response = request.response
        headers = response.generate_headers()
        headers = [(str(key), str(value)) for key, value in headers]
        key, status = headers.pop(0)
        assert key == 'Status'
        start_response(status, headers)
        self.publisher._clear_request()
        return [response.body,]  # Iterable object!
