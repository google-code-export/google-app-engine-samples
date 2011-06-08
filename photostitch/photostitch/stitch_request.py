#!/usr/bin/python2.4
#
# Copyright 2011 Google Inc. All Rights Reserved.

"""Class that handles a single Stitch Request."""

try:  # (code before imports) pylint: disable-msg=C6205
  import auto_import_fixer  # (unused import) pylint: disable-msg=W0611,C6204
except ImportError:
  pass

import os
import time

import boto
from boto.gs.key import Key

import config

from apiclient.anyjson import simplejson

_CHUNK_SIZE = 512 * 1024

class StitchRequest(object):

  def __init__(self, user, batch, bucket):
    self._user = user
    self._batch = batch
    self._files = []
    self._bucket = bucket

  def AddFile(self, filename, contents):
    part = 0
    bytes_left = len(contents)
    parts = []
    conn = boto.connect_gs(config.gs_access_key,config.gs_secret_key)
    bucket = conn.get_bucket(self._bucket)
    while bytes_left > 0:
      fname = '%s.%d' % (filename, part)
      parts.append(fname)
      offset = part * _CHUNK_SIZE
      k = Key(bucket, '%s/%s/input/%s' % (self._user, self._batch, fname))
      k.set_contents_from_string(
          contents[offset:offset+_CHUNK_SIZE])
      part += 1
      bytes_left -= _CHUNK_SIZE
    self._files.append({'name': filename, 'chunks': parts})

  def WriteState(self):
    state = {
      'status': 'WAITING',
      'update_time': time.time()
    }
    conn = boto.connect_gs(config.gs_access_key,config.gs_secret_key)
    bucket = conn.get_bucket(self._bucket)
    k = Key(bucket, '%s/%s/output/stitch.state' % (self._user, self._batch))
    k.set_contents_from_string(
        simplejson.dumps(state, indent=2),
        policy='public-read',headers={'Content-Type': 'text/plain'})

  def toJson(self):
    base = '%s/%s/%s' % (self._bucket, self._user, self._batch)
    return simplejson.dumps({ 'base': base, 'input_files': self._files })
