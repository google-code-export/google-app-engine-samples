#!/usr/bin/python
#
# Copyright 2008 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
A sample OpenID consumer app for Google App Engine. Allows users to log into
other OpenID providers, then displays their OpenID login. Also stores and
displays the most recent logins.

Part of http://code.google.com/p/google-app-engine-samples/.

For more about OpenID, see:
  http://openid.net/
  http://openid.net/about.bml

Uses JanRain's Python OpenID library, version 2.1.1, licensed under the
Apache Software License 2.0:
  http://openidenabled.com/python-openid/

The JanRain library includes a reference OpenID provider that can be used to
test this consumer. After starting the dev_appserver with this app, unpack the
JanRain library and run these commands from its root directory:

  setenv PYTHONPATH .
  python ./examples/server.py -s localhost

Then go to http://localhost:8080/ in your browser, type in
http://localhost:8000/test as your OpenID identifier, and click Verify.
"""

import cgi
import Cookie
import datetime
import logging
import os
import pickle
import pprint
import sys
import traceback
import urlparse
import wsgiref.handlers

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

from openid import fetchers
from openid.consumer.consumer import Consumer
from openid.consumer import discover
from openid.extensions import pape, sreg
import fetcher
import store

# Set to True if stack traces should be shown in the browser, etc.
_DEBUG = False


class Login(db.Model):
  """A completed OpenID login."""
  status = db.StringProperty(choices=('success', 'cancel', 'failure'))
  openid = db.LinkProperty()
  server = db.LinkProperty()
  timestamp = db.DateTimeProperty(auto_now_add=True)


class Session(db.Expando):
  """An in-progress OpenID login."""
  pass


class Handler(webapp.RequestHandler):
  """A base handler class with a couple OpenID-specific utilities."""
  consumer = None
  session = None

  def get_consumer(self):
    """Returns a Consumer instance.
    """
    if not self.consumer:
      fetchers.setDefaultFetcher(fetcher.UrlfetchFetcher())
      session = self.get_session()
      self.consumer = Consumer(vars(session), store.DatastoreStore())

    return self.consumer

  def args_to_dict(self):
    """Converts the URL and POST parameters to a singly-valued dictionary.

    Returns:
      dict with the URL and POST body parameters
    """
    req = self.request
    return dict([(arg, req.get(arg)) for arg in req.arguments()])

  def get_session(self):
    """Gets the current session.
    """
    if not self.session:
      id = self.request.get('session_id')
      if id:
        try:
          self.session = db.get(db.Key.from_path('Session', int(id)))
          assert self.session
        except (AssertionError, db.Error), e:
          self.report_error(str('Invalid session id: %d' % id))
      else:
        self.session = Session()

    return self.session

  def render(self, template_name, extra_values={}):
    """render the given template, including the extra (optional) values.

    Args:
      template_name: string
      The template to render.

      extra_values: dict
      Template values to provide to the template.
    """
    query = Login.gql('ORDER BY timestamp DESC')

    values = {
      'response': {},
      'openid': '',
      'logins': query.fetch(20),
      'request': self.request,
      'debug': self.request.get('deb'),
    }
    values.update(extra_values)
    cwd = os.path.dirname(__file__)
    path = os.path.join(cwd, 'templates', template_name + '.html')
    logging.debug(path)
    self.response.out.write(template.render(path, values, debug=_DEBUG))

  def report_error(self, message):
    """Shows an error HTML page.

    Args:
      message: string
      A detailed error message.
    """
    args = pprint.pformat(self.args_to_dict())
    self.render('error', vars())
    logging.error(message)

  def show_front_page(self):
    """Do an internal (non-302) redirect to the front page.

    Preserves the user agent's requested URL.
    """
    front_page = FrontPage()
    front_page.request = self.request
    front_page.response = self.response
    front_page.get()


class FrontPage(Handler):
  """Show the default OpenID page, with the last 10 logins for this user."""
  def get(self):
    self.render('index')


class LoginHandler(Handler):
  """Handles a POST response to the OpenID login form."""

  def post(self):
    """Handles login requests."""
    openid_url = self.request.get('openid')
    if not openid_url:
      self.show_front_page()

    try:
      auth_request = self.get_consumer().begin(openid_url)
    except discover.DiscoveryFailure, e:
      self.report_error(str(e))

    session = Session()
    session.put()

    sreg_request = sreg.SRegRequest(optional=['nickname', 'fullname', 'email'])
    auth_request.addExtension(sreg_request)

    pape_request = pape.Request([pape.AUTH_MULTI_FACTOR,
                                 pape.AUTH_MULTI_FACTOR_PHYSICAL,
                                 pape.AUTH_PHISHING_RESISTANT,
                                 ])
    auth_request.addExtension(pape_request)

    parts = list(urlparse.urlparse(self.request.uri))
    parts[2] = 'finish'
    parts[4] = 'session_id=%d' % session.key().id()
    parts[5] = ''
    return_to = urlparse.urlunparse(parts)
    realm = urlparse.urlunparse(parts[0:2] + [''] * 4)

#     logging.debug('Redirecting to %s' %
#                   auth_request.redirectURL(realm, return_to))
    self.redirect(auth_request.redirectURL(realm, return_to))


class FinishHandler(Handler):
  """Handle a redirect from the provider."""
  def get(self):
    args = self.args_to_dict()
    response = self.get_consumer().complete(args, self.request.uri)
    assert response.status in Login.status.choices

    if (response.status == 'success'):
      sreg_data = sreg.SRegResponse.fromSuccessResponse(response).items()
#     sreg_keys = sreg_data.keys()
#     sreg_values = sreg_data.values()
      pape_data = pape.Response.fromSuccessResponse(response)

#     print >> sys.stderr, response.status
    login = Login(status=response.status,
                  openid=response.endpoint.claimed_id,
                  server=response.endpoint.server_url)
    login.put()

    self.render('response', locals())
#     self.response.out.write(
#       '\r\n\r\n%s\n%s\r\n\r\n' % (response.status, response.message))



# Map URLs to our RequestHandler classes above
_URLS = [
  ('/', FrontPage),
  ('/login', LoginHandler),
  ('/finish', FinishHandler),
]

def main(argv):
  application = webapp.WSGIApplication(_URLS, debug=_DEBUG)
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main(sys.argv)
 
