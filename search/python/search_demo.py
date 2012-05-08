#!/usr/bin/python
#
# Copyright 2011 Google Inc. All Rights Reserved.

"""A simple guest book app that demonstrates the App Engine search API."""


from cgi import parse_qs
from datetime import datetime
import os
import string
import urllib
from urlparse import urlparse

from google.appengine.api import search
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

# contains a function to allow proper construction of sort options in both
# release 1.6.4 and 1.6.5+.  See code below.
import sortoptions


_INDEX_NAME = 'greeting'

_ENCODE_TRANS_TABLE = string.maketrans('-: .@', '_____')


class MainPage(webapp.RequestHandler):
    """Handles search requests for comments."""

    def get(self):
        """Handles a get request with a query."""
        uri = urlparse(self.request.uri)
        query = ''
        if uri.query:
            query = parse_qs(uri.query)
            query = query['query'][0]

        # sort results by author descending
        expr_list = [search.SortExpression(
            expression='author', default_value='',
            direction=search.SortExpression.DESCENDING)]
        # construct the sort options value using the get_sort_options() wrapper
        # function, which will work correctly in both release 1.6.4 and
        # release 1.6.5+.
        sort_opts = sortoptions.get_sort_options(
            expr_list, match_scorer=None)
        query_options = search.QueryOptions(
            limit=3,
            sort_options=sort_opts)
        query_obj = search.Query(query_string=query, options=query_options)
        results = search.Index(name=_INDEX_NAME).search(query=query_obj)

        if users.get_current_user():
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'

        template_values = {
            'results': results,
            'number_returned': len(results.results),
            'url': url,
            'url_linktext': url_linktext,
        }

        path = os.path.join(os.path.dirname(__file__), 'index.html')
        self.response.out.write(template.render(path, template_values))


def CreateDocument(author, content):
    """Creates a search.Document from content written by the author."""
    if author:
        nickname = author.nickname().split('@')[0]
    else:
        nickname = 'anonymous'
    # Let the search service supply the document id.
    return search.Document(
        fields=[search.TextField(name='author', value=nickname),
                search.TextField(name='comment', value=content),
                search.DateField(name='date', value=datetime.now().date())])


class Comment(webapp.RequestHandler):
    """Handles requests to index comments."""

    def post(self):
        """Handles a post request."""
        author = None
        if users.get_current_user():
            author = users.get_current_user()

        content = self.request.get('content')
        query = self.request.get('search')
        if content:
            search.Index(name=_INDEX_NAME).add(CreateDocument(author, content))
        if query:
            self.redirect('/?' + urllib.urlencode(
                #{'query': query}))
                {'query': query.encode('utf-8')}))
        else:
            self.redirect('/')


application = webapp.WSGIApplication(
    [('/', MainPage),
     ('/sign', Comment)],
    debug=True)


def main():
    run_wsgi_app(application)

if __name__ == '__main__':
    main()
