#!/usr/bin/python2.5
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Handle incoming email for Cloud Photo Stitcher.

Expects a zip file of images and stitches them.

mail to  batch_name@photostitch.appspot.com.
"""

try:  # (code before imports) pylint: disable-msg=C6205
  import auto_import_fixer  # (unused import) pylint: disable-msg=W0611,C6204
except ImportError:
  pass

import logging
import email

import config
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from google.appengine.ext.webapp.mail_handlers import InboundMailHandler
from google.appengine.ext.webapp.util import run_wsgi_app
from stitch_request import StitchRequest

class EmailHandler(InboundMailHandler):
  def receive(self, mail_message):
    logging.info("Received a message from: " + mail_message.sender)
    images = mail_message.bodies('image/jpeg')
    req = StitchRequest(mail_message.sender, 'batchx', config.gs_bucket)
    for file, attachment in mail_message.attachments:
      logging.info('attachment: %s' % file)
      file = file.lower().replace(' ', '')
      if not (file.endswith('.jpg') or file.endswith('.jpeg')):
        continue
      logging.info('writing %s, %d bytes' % (file, len(attachment)))
      req.AddFile(file, attachment)
    logging.info('%s' % req.toJson())

def main():
  application = webapp.WSGIApplication([EmailHandler.mapping()],
                                       debug=True)
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()
