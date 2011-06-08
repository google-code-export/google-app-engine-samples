#!/usr/bin/python2.5
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Handler for Cloud Photo Stitcher.

This module handles the web interface to the photo stitcher.
"""

import logging
import os
import re

import boto
import config

from apiclient.anyjson import simplejson
from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp import util
from google.appengine.ext.webapp.util import login_required
from boto.gs.connection import GSConnection


class MainHandler(webapp.RequestHandler):
  """Default handler."""

  # (get is not allowed by Google naming convention) pylint: disable-msg=C6409
  @login_required
  def get(self):
    """Handle GET requests.

    For the time being, we just provide an information page.  In the future
    there will be a web UI here.
    """
    path = os.path.join(os.path.dirname(__file__), 'index.html')
    user = users.get_current_user()

    connection = GSConnection(config.gs_access_key,config.gs_secret_key)
    bucket = connection.get_bucket(config.gs_bucket)

    # Find all of the batches.
    batches = []
    logging.info('Loading batches')
    rs = bucket.list(prefix=user.email() + '/', delimiter='/')
    for r in rs:
      logging.info(r.name)
      batch_name = r.name.split('/')[1]
      batches.append(self.LoadBatchInfo(user.email(), batch_name, bucket))
    batches.sort(key=lambda i: i.get('update_time', 0), reverse=True)
    self.response.out.write(
        template.render(path, {
            'url': self.request.url,
            'user_id': user.user_id(),
            'email': user.email(),
            'batches': batches,
            }))

  def LoadBatchInfo(self, user_email, batch_name, bucket):
    logging.info('Loading batch info: %s' % batch_name)
    output_prefix = '%s/%s/output/'
    key = bucket.get_key('%s/%s/output/stitch.state' % (user_email, batch_name))
    if key:
      batch_info = simplejson.loads(key.get_contents_as_string())
      batch_info['name'] = batch_name
      return batch_info
    return { 'name': batch_name, 'status': 'WAITING', 'update_time': 0.0 }



def main():
  application = webapp.WSGIApplication([
      ('/', MainHandler),
      ],
      debug=True)
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()
