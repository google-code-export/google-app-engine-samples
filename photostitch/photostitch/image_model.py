#!/usr/bin/python2.4
#
# Copyright 2011 Google Inc. All Rights Reserved.

"""Model for image objects

Cached files are a map of a filename to a blob of contents.
"""

try:  # (code before imports) pylint: disable-msg=C6205
  import auto_import_fixer  # (unused import) pylint: disable-msg=W0611,C6204
except ImportError:
  pass

from google.appengine.ext import db

class ImageModel(db.Model):
  filename = db.StringProperty(name='filename', required=True, indexed=True)
  contents = db.BlobProperty(name='contents', required=True)
  timestamp = db.DateTimeProperty(auto_now=True)
