# Copyright (C) 2008 Google Inc.
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


__author__ = 'api.jscudder (Jeff Scudder)'


import wsgiref.handlers
from google.appengine.ext import webapp
from google.appengine.api import users
import atom.url
import gdata.service
import gdata.alt.appengine
import settings


class Fetcher(webapp.RequestHandler):

  def get(self):
    # Write our pages title
    self.response.out.write("""<html><head><title>
        Google Data Feed Fetcher: read Google Data API Atom feeds</title>""")
    self.response.out.write('</head><body>')
    # Allow the user to sign in or sign out
    next_url = atom.url.Url('http', settings.HOST_NAME, path='/step2')
    if users.get_current_user():
      self.response.out.write('<a href="%s">Sign Out</a><br>' % (
          users.create_logout_url(str(next_url))))
    else:
      self.response.out.write('<a href="%s">Sign In</a><br>' % (
          users.create_login_url(str(next_url))))

    # Initialize a client to talk to Google Data API services. 
    client = gdata.service.GDataService()
    gdata.alt.appengine.run_on_appengine(client)

    session_token = None
    # Find the AuthSub token and upgrade it to a session token.
    auth_token = gdata.auth.extract_auth_sub_token_from_url(self.request.uri)
    if auth_token:
      # Upgrade the single-use AuthSub token to a multi-use session token.
      session_token = client.upgrade_to_session_token(auth_token)
    if session_token and users.get_current_user():
      # If there is a current user, store the token in the datastore and
      # associate it with the current user. Since we told the client to
      # run_on_appengine, the add_token call will automatically store the
      # session token if there is a current_user.
      client.token_store.add_token(session_token)
    elif session_token:
      # Since there is no current user, we will put the session token
      # in a property of the client. We will not store the token in the
      # datastore, since we wouldn't know which user it belongs to.
      # Since a new client object is created with each get call, we don't
      # need to worry about the anonymous token being used by other users.
      client.current_token = session_token

    self.response.out.write('<div id="main"></div>')
    self.response.out.write(
        '<div id="sidebar"><div id="scopes"><h4>Request a token</h4><ul>')
    self.response.out.write('<li><a href="%s">Google Documents</a></li>' % (
        client.GenerateAuthSubURL(
            next_url, 
            ('http://docs.google.com/feeds/',), secure=False, session=True)))
    self.response.out.write('</ul></div><br/><div id="tokens">')


def main():
  application = webapp.WSGIApplication([('/.*', Fetcher),], debug=True)
  wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()
