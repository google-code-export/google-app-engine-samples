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


__author__ = 'api.jscudder (Jeffrey Scudder)'


import cgi
import wsgiref.handlers
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.api import urlfetch
import urllib # Used to unescape URL parameters.
import gdata.service
import gdata.alt.appengine
import gdata.auth
import atom
import atom.http_interface
import atom.token_store
import atom.url
import settings


class Fetcher(webapp.RequestHandler):

  def get(self):
    self.response.headers['Content-Type'] = 'text/html'
    
    self.response.out.write("""<!DOCTYPE html><html><head>
         <title>Google Data Feed Fetcher: read Google Data API Atom feeds
         </title>
         <link rel="stylesheet" type="text/css" 
               href="static/feedfetcher.css"/>
         </head><body>""")
       
    self.response.out.write("""<div id="nav"><a href="/">Home</a>""")
    if users.get_current_user():
      self.response.out.write('<a href="%s">Sign Out</a>' % (
          users.create_logout_url('http://%s/' % settings.HOST_NAME)))
    else:
      self.response.out.write('<a href="%s">Sign In</a>' % (
          users.create_login_url('http://%s/' % settings.HOST_NAME)))
    self.response.out.write('</div>')

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

    # Get the URL for the desired feed and get the display option.
    feed_url = self.request.get('feed_url')
    erase_tokens = self.request.get('erase_tokens')
    if erase_tokens:
      self.EraseStoredTokens()
    show_xml = self.request.get('xml')

    if show_xml:
      checked_string = 'checked'
    else:
      checked_string = ''
      
    self.response.out.write("""<div id="wrap"><div id="header">
          <h1>Google Data Feed Fetcher</h1>
          <form action="/" method="get">
          <label id="feed_url_label" for="feed_url">Target URL:</label>
          <input type="text" size="60" name="feed_url" id="feed_url" 
              value="%s"></input>
          <input type="submit" value="Fetch Atom"></input>
          <label for="xml">Show XML:</label>
          <input type="checkbox" id="xml" name="xml" value="true" %s></input>
        </form></div>""" % ((feed_url or ''), checked_string))

    self.response.out.write('<div id="main">')
    if not feed_url:
      self.ShowInstructions()
    else:
      self.FetchFeed(client, feed_url, show_xml)
    self.response.out.write('</div>')

    if users.get_current_user():
      self.response.out.write("""<div id="sidebar"><div id="scopes">
          <h4>Request a token for some common scopes</h4><ul>
          <li><a href="%s">Blogger</a></li>
          <li><a href="%s">Calendar</a></li>
          <li><a href="%s">Google Documents</a></li>
          </ul></div><div id="tokens">""" % (
              self.GenerateScopeRequestLink(client, 
                  'http://www.blogger.com/feeds/'),
              self.GenerateScopeRequestLink(client, 
                  'http://www.google.com/calendar/feeds'),
              self.GenerateScopeRequestLink(client, 
                  'http://docs.google.com/feeds/')))

      self.DisplayAuthorizedUrls()
      self.response.out.write('</div>')
    self.response.out.write('</div></div></body></html>')
    
  def GenerateScopeRequestLink(self, client, scope):
    return client.GenerateAuthSubURL('http://%s/' % (
            settings.HOST_NAME,),
        scope, secure=False, session=True)

  def ShowInstructions(self):
    self.response.out.write("""<p>This sample application illustrates the
        use of <a 
        href="http://code.google.com/apis/accounts/docs/AuthForWebApps.html">
        AuthSub authentication</a> to access 
        <a href="http://code.google.com/apis/gdata/">Google Data feeds</a>.</p>

        <p>To start using this sample, you can enter the URL for an Atom feed
        or entry in the input box above, or you can click on one of the 
        example feeds below. Some of these feeds require you to authorize this
        app to have access. To avoid authorizing over and over, sign in to
        this application above and previous authorization tokens will be stored
        for future use.</p>

        <h4>Sample Feed URLs</h4>
        <h5>Publicly viewable feeds</h5>
        <ul><li><a href="%s"
        >Recent posts in the Google App Engine blog</a></li>
        <li><a href="%s"
        >Recent posts in the Google Data APIs blog</a></li>
        <li><a href="%s"
        >See events on the Google Developer Events calendar</a></li></ul>
        <h5>Feeds which require authorization</h5>
        <ul><li><a href="%s"
        >List your Google Documents</a></li>
        <li><a href="%s"
        >List the Google Calendars that you own</a></li>
        <li><a href="%s"
        >List your Google Calendars</a></li>
        <li><a href="%s"
        >List your blogs on Blogger</a></li>
        <!--<li><a href="%s"
        >List your Gmail Contacts</a></li>--></ul>
        
        <p>To learn more about how this sample works, read the article on
        <a href="http://code.google.com/appengine/articles/gdata.html"
        >Retrieving Authenticated Google Data Feeds with
        Google App Engine</a>.</p>
 
        <p>In addition to reading information in Google Data feeds, 
        it is also possible to write to some of the Google Data services
        once the user has granted permission to your app. For more details
        on the capabilities of the different Google Data service see the
        <a href="http://code.google.com/apis/gdata/">home page</a> for 
        Google Data APIs.</p>

        <p>This app uses the <a 
        href="http://code.google.com/p/gdata-python-client/"
        >gdata-python-client</a> library.</p>
    """ % (
        self.GenerateFeedRequestLink(
            'http://www.blogger.com/feeds/8501956666581132164/posts/default'),
        self.GenerateFeedRequestLink(
            'http://googledataapis.blogspot.com/feeds/posts/default'),
        self.GenerateFeedRequestLink(
            'http://www.google.com/calendar/feeds/developer-calendar@google.com/public/basic'),
        self.GenerateFeedRequestLink(
            'http://docs.google.com/feeds/documents/private/full'),
        self.GenerateFeedRequestLink(
            'http://www.google.com/calendar/feeds/default/owncalendars/full'),
        self.GenerateFeedRequestLink(
            'http://www.google.com/calendar/feeds/default/allcalendars/full'),
        self.GenerateFeedRequestLink(
            'http://www.blogger.com/feeds/default/blogs'),
        self.GenerateFeedRequestLink(
            'http://www.google.com/m8/feeds/contacts/default/base')))

  def GenerateFeedRequestLink(self, feed_url):
    return atom.url.Url('http', settings.HOST_NAME, path='/', 
        params={'feed_url':feed_url}).to_string()

  def FetchFeed(self, client, feed_url, show_xml=False):
    # Attempt to fetch the feed.
    try:
      if show_xml:
        response = client.Get(feed_url, converter=str)
        response = response.decode('UTF-8')
        self.response.out.write(cgi.escape(response))
      else:
        response = client.Get(feed_url)
        if isinstance(response, atom.Feed):
          self.RenderFeed(response)
        elif isinstance(response, atom.Entry):
          self.RenderEntry(response)
        else:
          self.response.out.write(cgi.escape(response.read()))
    except gdata.service.RequestError, request_error:
      # If fetching fails, then tell the user that they need to login to
      # authorize this app by logging in at the following URL.
      if request_error[0]['status'] == 401:
        # Get the URL of the current page so that our AuthSub request will
        # send the user back to here.
        next = self.request.uri
        auth_sub_url = client.GenerateAuthSubURL(next, feed_url,
            secure=False, session=True)
        self.response.out.write('<a href="%s">' % (auth_sub_url))
        self.response.out.write(
            'Click here to authorize this application to view the feed</a>')
      else:
        self.response.out.write(
            'Something else went wrong, here is the error object: %s ' % (
                str(request_error[0])))

  def RenderFeed(self, feed):
    self.response.out.write('<h2>Feed Title: %s</h2>' % (
        feed.title.text.decode('UTF-8')))
    for link in feed.link:
      self.RenderLink(link)
    for entry in feed.entry:
      self.RenderEntry(entry)

  def RenderEntry(self, entry):
    self.response.out.write('<h3>Entry Title: %s</h3>' % (
        entry.title.text.decode('UTF-8')))
    if entry.content and entry.content.text:
      self.response.out.write('<p>Content: %s</p>' % (
          entry.content.text.decode('UTF-8')))
    elif entry.summary and entry.summary.text:
      self.response.out.write('<p>Summary: %s</p>' % (
          entry.summary.text.decode('UTF-8')))
    for link in entry.link:
      self.RenderLink(link)

  def RenderLink(self, link):
    if link.rel == 'alternate' and link.type == 'text/html':
      self.response.out.write(
          'Link: <a href="%s">alternate HTML</a><br/>' % link.href)
    elif link.type == 'application/atom+xml':
      self.response.out.write(
          'Link: <a href="/?feed_url=%s">Fetch %s link (%s)</a><br/>' % (
              urllib.quote_plus(link.href), link.rel, link.type))
    else:
      self.response.out.write(
          'Link: <a href="%s">%s link (%s)</a><br/>' % (link.href, link.rel,
              link.type))
    
  def DisplayAuthorizedUrls(self):
    self.response.out.write('<h4>Stored Authorization Tokens</h4><ul>')
    tokens = gdata.alt.appengine.load_auth_tokens()
    for token_scope in tokens:
      self.response.out.write('<li><a href="/?feed_url=%s">%s*</a></li>' % (
          urllib.quote_plus(str(token_scope)), str(token_scope)))
    self.response.out.write(
        '</ul>To erase your stored tokens, <a href="%s">click here</a>' % (
            atom.url.Url('http', settings.HOST_NAME, path='/', 
                params={'erase_tokens':'true'}).to_string()))

  def EraseStoredTokens(self):
    gdata.alt.appengine.save_auth_tokens({})


class Acker(webapp.RequestHandler):
  """Simulates an HTML page to prove ownership of this domain for AuthSub 
  registration."""

  def get(self):
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.out.write('This file present for AuthSub registration.')


def main():
  application = webapp.WSGIApplication([('/', Fetcher), 
      ('/google72db3d6838b4c438.html', Acker)], 
      debug=True)
  wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()
