#!/usr/bin/python
#
# Copyright 2011 Google Inc.
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

"""A guestbook sample app for Google Cloud SQL.

Deployed at http://sql-guestbook.appspot.com/

Schema:

CREATE TABLE `Greetings` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `author` varchar(32) DEFAULT NULL,
  `date` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `content` varchar(512) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `date` (`date`)
) DEFAULT CHARSET=utf8;
"""

import cgi
import datetime
import sys

from google.appengine.api import rdbms
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util

# rdbms db-api connection, globally cached
conn = None
DEBUG = True
DATABASE_NAME = 'guestbook'
INSTANCE ='google.com:speckle-python-demos:sqlguestbook-55'

_PARAM_MARKERS = { 'qmark': '?', 'format': '%s' }
MARKER = _PARAM_MARKERS[rdbms.paramstyle]


class Guestbook(webapp.RequestHandler):
  def __init__(self):
    super(Guestbook, self).__init__()

  def get(self):
    """HTTP GET. Render the guestbook.
    """
    self.Render()

  def Render(self):
    """Render all of the posts in the datastore.
    """
    self.response.out.write(HEADER)

    cursor = conn.cursor()
    cursor.execute(
        'SELECT author, date, content FROM Greetings ORDER BY date DESC LIMIT 10')
    for author, date, content in cursor.fetchall():
      self.response.out.write("""
      <p class="signature"> %s
      <br />
      <i>&nbsp;&nbsp;-%s, %s UTC</i></p>
      """ % (content, author, date))

    self.response.out.write(FOOTER)

  def post(self):
    """HTTP POST. Store a new message, then render the guestbook.
    """
    cursor = conn.cursor()
    query = 'INSERT INTO Greetings (author, date, content) VALUES(%s, %s, %s)' \
        % (MARKER, MARKER, MARKER)
    cursor.execute(query,
                   (cgi.escape(self.request.get('author')),
                    rdbms.Timestamp(*datetime.datetime.now().timetuple()[:6]),
                    cgi.escape(self.request.get('content', default_value= ''))))
    conn.commit()

    self.response.set_status(302)
    self.response.headers['Location'] = '/'


def main(argv):
  application = webapp.WSGIApplication([('.*', Guestbook)], debug=DEBUG)
  global conn
  conn = rdbms.connect(instance=INSTANCE, database=DATABASE_NAME)
  util.run_wsgi_app(application)


HEADER = """
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
"http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html>
<head>
<title> Cloud SQL Guestbook </title>
<style type="text/css">
body {
  width: 500px;
  margin: 15px;
}

p.signature, div.form {
  padding: 10px;
  border: 1px solid Navy;
  width: auto;
}

p.signature { background-color: Ivory; }
div.form { background-color: LightSteelBlue; }
</style>
</head>

<body>
<div id="main">
<div id="body">

<h1> Cloud SQL Guestbook </h1>

<p style="font-style: italic">
This is a sample Python app
(<a href="http://code.google.com/p/google-app-engine-samples/source/browse/#svn/trunk/sql-guestbook">source</a>)
for <a href="https://code.google.com/apis/sql/">Google Cloud SQL</a>.
</p>

<hr />
<div class="form">
Sign the guestbook!

<form action="/post" method="POST">
<table>
<tr><td> Name: </td><td><input type="text" name="author"</td></tr>
<td> Message: </td><td><input type="textarea" name="content"</td></tr>
<td /><td><input type="submit" value="Sign"></td>
</table>
</form>
</div>
"""

FOOTER = """
</div></div>
</body>
</html>
"""

if __name__ == '__main__':
  main(sys.argv)
