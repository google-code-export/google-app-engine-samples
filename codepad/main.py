#!/usr/bin/env python
#
# Copyright 2011 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.ext.webapp import util
from google.appengine.ext.webapp import template
from google.appengine.api import namespace_manager

import os

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), 'index.html')


class Pad(db.Model):
    """
    Store source code and a link to a previous revisions.
    """
    code = db.TextProperty(required=True)
    parent_pad = db.SelfReferenceProperty()


class EditHandler(webapp.RequestHandler):
    """
    Build the form to edit source code, and handle submission.
    """

    def get(self, pad_id):
        pad = Pad.get_by_id(int(pad_id)) if pad_id else None
        self.response.out.write(template.render(TEMPLATE_PATH, {'pad': pad}))

    def post(self, parent_id):
        code = self.request.get('code').replace('\r\n', '\n')
        parent_pad = Pad.get_by_id(int(parent_id)) if parent_id else None
        if not parent_pad or parent_pad.code != code:
          pad = Pad(code=code, parent_pad=parent_pad)
          pad_key = pad.put()
        else:
          pad_key = parent_pad.key()
        self.redirect('/%s' % pad_key.id())


class MainHandler(webapp.RequestHandler):
    """
    Evaluate source code in the iframe.
    Named 'MainHandler' to match the code included in the template.
    """

    def get(self, pad_id):
        pad = Pad.get_by_id(int(pad_id))
        namespace_manager.set_namespace(pad_id)
        exec(pad.code, {'webapp': webapp}, {'self': self})

application = webapp.WSGIApplication([('/(\d+)/eval', MainHandler),
                                      ('/(\d*)', EditHandler)],
                                     debug=True)


def main():
    util.run_wsgi_app(application)

if __name__ == '__main__':
    main()
