# Copyright 2008 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import wsgiref.handlers
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template


class IndexController(webapp.RequestHandler):
  """Controller that handles the front page."""

  def get(self):
    path = os.path.join(os.curdir, '..', 'templates', 'index.html')
    values = {
        'app_jid': os.environ['SERVER_NAME'].replace('.', '@', 1),
    }
    self.response.out.write(template.render(path, values))


def main():
  app = webapp.WSGIApplication([
      ('/', IndexController),
      ], debug=True)
  wsgiref.handlers.CGIHandler().run(app)


if __name__ == '__main__':
  main()
