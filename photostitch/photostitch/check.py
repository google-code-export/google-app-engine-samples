#!/usr/bin/python2.4
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Check upload status

"""

try:  # (code before imports) pylint: disable-msg=C6205
  import auto_import_fixer  # (unused import) pylint: disable-msg=W0611,C6204
except ImportError:
  pass

import cStringIO
import logging
import zipfile

import taskqueue
import config
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from stitch_request import StitchRequest

class CheckHandler(webapp.RequestHandler):
  """Handler for library code generation requests."""

  # (get is not allowed by Google naming convention) pylint: disable-msg=C6409
  def get(self, batch='stitched'):
    """Handle HTTP POST requests."""
    batch = self.request.get('batch') or batch
    logging.info('batch name: %s' % batch)
    # for non-multipart
    #data = self.request.body_file
    data = cStringIO.StringIO(self.request.get('file'))
    archive = zipfile.ZipFile(data, 'r')
    user = users.get_current_user()
    req = StitchRequest(user.email(), batch, config.gs_bucket)
    for info in archive.infolist():
      # 2.6 image = archive.open(info.filename).read()
      image = archive.read(info.filename)
      logging.info('%s/%d bytes' % (info.filename, len(image)))
      req.AddFile(info.filename, image)
    logging.info('%s' % req.toJson())
    q = taskqueue.Queue('photostitch')
    tasks = []
    tasks.append(taskqueue.Task(payload=req.toJson(), method='PULL'))
    q.add(tasks)


def main():
  application = webapp.WSGIApplication(
      [(r'.*/?check/(\w+)?', CheckHandler)],
      debug=True)
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()
