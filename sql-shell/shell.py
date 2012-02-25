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

"""An AJAX SQL shell sample app for Google Cloud SQL.

Deployed at http://sql-shell.appspot.com/
"""

import logging

from google.appengine.api import rdbms
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util


# rdbms db-api connection, globally cached
conn = None
DEBUG = True
DATABASE_NAME = 'shell'
INSTANCE ='google.com:speckle-python-demos:sqlshell-55'


class StatementHandler(webapp.RequestHandler):
  """Runs a SQL statement and returns the result."""

  def get(self):
    self.response.headers['Content-Type'] = 'text/plain'

    statement = self.request.get('statement')
    if not statement:
      return

    try:
      cursor = conn.cursor()
      logging.info('Executing %r' % statement)
      cursor.execute(statement)
      for results in cursor.fetchall():
        self.response.out.write('%s\r\n' % str(results))
      conn.commit()
    except rdbms.Error, e:
      logging.exception('Error:')
      self.response.out.write(str(e))


def main():
  global conn
  conn = rdbms.connect(instance=INSTANCE, database=DATABASE_NAME)
  application = webapp.WSGIApplication([('/shell.do', StatementHandler)],
                                       debug=DEBUG)
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()
