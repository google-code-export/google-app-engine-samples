#! /usr/bin/python

"""Simple driver to stitch drivers.

This is built to be run with gtaskqueue_puller. The first two arguments are
the input file and an output file. The output file is optionally posted back
to the service and contains a log of the execution."""

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time

import config
import boto

WORKING_DIR_BASE=os.path.expanduser('~/work')
LOG_DIR_BASE=os.path.expanduser('~/logs')

logger = logging.getLogger('stitch')
log_filename = None

class Error(Exception):
    """Base class for exceptions in this module."""
    pass
    

def RunCommand(*cmd, **kwargs):
  """Run a command in a separate process.

  Args:
    cmd: The command to be run
    kwargs: 
      input: stdin to process
      cwd: Execute in this directory
    
  Returns:
    (return code, output) where output is the combined 
    stderr/stdout stream from command
  """
  cmd = list(cmd)

  input_string = kwargs.get('input', None)
  cwd = kwargs.get('cwd', None)
  
  stdin_type = None
  if input_string:
    stdin_type = subprocess.PIPE

  logger.info('Running: %s', cmd)

  p = subprocess.Popen(
      cmd, stdin=stdin_type, 
      stdout=subprocess.PIPE, 
      stderr=subprocess.STDOUT, cwd=cwd)
  (output, _) = p.communicate(input_string)
  return (p.returncode, output)


class Stitcher(object):
  """Takes job description, stitches and uploads results.
  
  The input file is of the form like:
  {
    "base": "photostitch-test/user@domain.com/test1",
    "input_files": [
      {
        "name": "photo 1.JPG",
        "chunks": [ "photo 1.JPG.0", "photo 1.JPG.1", "photo 1.JPG.2", "photo 1.JPG.3" ]
      },
      {
        "name": "photo 2.JPG",
        "chunks": [ "photo 2.JPG.0", "photo 2.JPG.1", "photo 2.JPG.2", "photo 2.JPG.3" ]
      },
      {
        "name": "photo 3.JPG",
        "chunks": [ "photo 3.JPG.0", "photo 3.JPG.1", "photo 3.JPG.2", "photo 3.JPG.3" ]
      }
    ]
  }

  This class will download
  "http://commondatastorage.googleapis.com/<base>/input/photo ?.JPG.?",
  concate parts together to create full file, run panoramic stitching and then
  upload the result back up to Google storage.
  """
  def __init__(self, task_doc, output_file):
    self.task_doc = task_doc
    self.output_file = output_file
    self.input_files = {}
    self.input_thumbs = {}
    self.request = None
    self.base = None
    self.conn = boto.connect_gs(config.gs_access_key, config.gs_secret_key)
    self.bucket = self.conn.get_bucket(config.gs_bucket)
  
  def Stitch(self):
    self._CreateWorkDir()
    try:
      self._ParseTaskDoc()
      self._SetStatus('DOWNLOADING')
      self._DownloadFiles()
      self._CreateInputThumbs()
      self._UploadMergedInput()
      self._SetStatus('STITCHING')
      self._Stitch()
      self._Upload()
      self._SetStatus('DONE')
    except Exception, err:
      logger.exception('Exception while stitching')
      self._SetStatus('FAILED')
      return -1
    finally:
      self._UploadLog()
      # self._DeleteWorkDir()
    return 0
  
  def _CreateWorkDir(self):
    if not os.path.exists(WORKING_DIR_BASE):
      os.makedirs(WORKING_DIR_BASE) 
    self.working_dir = tempfile.mkdtemp(dir=WORKING_DIR_BASE)
    logger.info("Work dir: %s", self.working_dir)
    
  def _DeleteWorkDir(self):
    logger.info("Deleting: %s", self.working_dir)
    shutil.rmtree(self.working_dir)
    
  def _ParseTaskDoc(self):
    with open(self.task_doc) as f:
      self.request = json.load(f)
      logging.info(json.dumps(self.request))
      self.base = self.request['base']
    
  def _SetStatus(self, status):
    if self.base:
      uri_string = 'gs://%s/output/stitch.status' % self.base
      logger.info('Setting status %s to %s', status, uri_string)
      uri = boto.storage_uri(uri_string)
      uri.connect(config.gs_access_key,config.gs_secret_key)
      uri.new_key().set_contents_from_string(
          status, policy='public-read', headers={'Content-Type': 'text/plain'})
          
      # Construct a state object to upload
      state = {}
      state['status'] = status
      state['update_time'] = time.time()
      state['output_base'] = '%s/output' % self.base
      state['input'] = [{ 'full': os.path.basename(i), 'thumb': os.path.basename(t)} 
          for (i, t) in zip(self.input_files, self.input_thumbs)]
      if status == 'DONE':
        state['output'] = { 'full': 'stitch.jpg', 'thumb': 'stitch-thumb.jpg' }
      if status in ('DONE', 'FAILED'):
        state['log'] = 'stitch.log'
      uri_string = 'gs://%s/output/stitch.state' % self.base
      state_json = json.dumps(state, indent=2)
      logger.info('Uploading state to %s\n%s', uri_string, state_json)
      uri = boto.storage_uri(uri_string)
      uri.connect(config.gs_access_key,config.gs_secret_key)
      uri.new_key().set_contents_from_string(
          state_json, policy='public-read', headers={'Content-Type': 'text/plain'})
    else:
      logger.error('No upload path for status %s', status)
      
  def _UploadLog(self):
    if self.base:
      uri_string = 'gs://%s/output/stitch.log' % self.base
      logger.info('Uploading log to %s', uri_string)
      uri = boto.storage_uri(uri_string)
      uri.connect(config.gs_access_key,config.gs_secret_key)
      uri.new_key().set_contents_from_filename(
          log_filename, policy='public-read',headers={'Content-Type': 'text/plain'})
    else:
      logger.error('No upload path for log file')
  
  def _DownloadFiles(self):
    self.input_files = []
    
    for (i, input_file) in enumerate(self.request['input_files']):
      input_name = input_file['name']
      chunks = input_file['chunks']
      (_, ext) = os.path.splitext(input_name)
      output_name = os.path.join(self.working_dir, 'input%03d%s' % (i, ext))
      with open(output_name, 'wb') as output_file:
        for chunk in chunks:      
          uri_string = 'gs://%s/input/%s' % (self.base, chunk)
          logger.info('Saving %s to %s', uri_string, output_name)
          uri = boto.storage_uri(uri_string)
          uri.connect(config.gs_access_key,config.gs_secret_key)
          uri.get_key().get_contents_to_file(output_file)
      self.input_files.append(output_name)
      
  def _CreateInputThumbs(self):
    self.input_thumbs = []
    for input_filename in self.input_files:
      thumb_filename = self._MakeThumb(input_filename)
      self.input_thumbs.append(thumb_filename)
      
  def _MakeThumb(self, filename):
    (base, ext) = os.path.splitext(filename)
    thumb_filename = '%s-thumb%s' % (base, ext)
    self._RunCommand('convert', filename, '-thumbnail', '200x200', thumb_filename)
    return thumb_filename
    
  def _UploadOutputJpg(self, filename):
    uri_string = 'gs://%s/output/%s' % (self.base, os.path.basename(filename))
    logger.info('Uploading file to %s', uri_string)
    uri = boto.storage_uri(uri_string)
    uri.connect(config.gs_access_key,config.gs_secret_key)
    uri.new_key().set_contents_from_filename(
        filename, policy='public-read', headers={'Content-Type': 'image/jpeg'})

  def _UploadMergedInput(self):
    for fn in self.input_files + self.input_thumbs:
      self._UploadOutputJpg(fn)
  
  def _RunCommand(self, *cmd):
    (return_code, output) = RunCommand(*cmd, cwd=self.working_dir)
    logger.info('Return Code: %d', return_code)
    logger.info('Command Output:\n%s', output)
    if return_code != 0:
      error_string = 'Command failed\n  Command: %s\n  Error: %d' % (cmd, return_code)
      logger.error(error_string)
      raise Error(error_string)
    
  def _Stitch(self):
    def IncrementName(name):
      parts = name.split('.')
      parts[1] = str(int(parts[1]) + 1)
      return '.'.join(parts)
      
    current = None
    next = 'pano.1.pto'
    first = next

    # Import images
    self._RunCommand('match-n-shift',
                     '-o', next,
                     *self.input_files)
    current = next
    next = IncrementName(current)
    
    technique = 'PTOANCHOR'
    
    if technique == 'PTOANCHOR':
      # Do all steps to generate points and optimize
      self._RunCommand('ptoanchor', '--output', next, current)
      current = next
      next = IncrementName(current)
    elif technique == 'MANUAL':
      # Tried and true point generation
      self._RunCommand('autopano-sift-c',
                       #'--refine', '--keep-unrefinable', 'on',
                       '--align',
                       '--ransac', 'on', '--maxmatches', '40',
                       next, current)
      current = next
      next = IncrementName(current)

      # self._RunCommand('ptomerge', first, current, next)
      # current = next
      # next = IncrementName(current)
    
      self._RunCommand('ptovariable', '--pitch', '--yaw', current)
      self._RunCommand('autooptimiser', '-o', next, '-n', current)
      current = next
      next = IncrementName(current)
    
      self._RunCommand('ptovariable', '--positions', '--view', '--barrel', current)    
      self._RunCommand('autooptimiser', '-o', next, '-l', '-s', '-n', current)
      current = next
      next = IncrementName(current)
    
    self._RunCommand('pto2mk', '-o', 'pano.pto.mk', '-p', 'pano', current)
    self._RunCommand('make', '-j', '8', '-e', '-f', 'pano.pto.mk', 'pano.tif')
    
    self._RunCommand('convert', '-trim', 'pano.tif', 'stitch.jpg')
    
  def _Upload(self):
    output_filename = os.path.join(self.working_dir, 'stitch.jpg')
    if not os.path.exists(output_filename):
      raise Error("No output produced.  Can't find stitch.jpg")
    output_thumb = self._MakeThumb(output_filename)
    self._UploadOutputJpg(output_filename)
    self._UploadOutputJpg(output_thumb)


def main(argv):
  task_doc = argv[1]
  output_file = argv[2]
  
  # Set up the logger to go to both the output file and a file in our working
  # directory.  We pick a file based on the start time and our process ID.
  global log_filename 
  log_filename = os.path.join(LOG_DIR_BASE, '%s-%d' % (time.strftime('%Y%m%d-%H%M%S'), os.getpid()))
  if not os.path.exists(LOG_DIR_BASE):
    os.makedirs(LOG_DIR_BASE)
  logger.setLevel(logging.DEBUG)
  logger.addHandler(logging.FileHandler(output_file))
  logger.addHandler(logging.FileHandler(log_filename))
  logger.addHandler(logging.StreamHandler())
  
  stitcher = Stitcher(task_doc, output_file)
  return stitcher.Stitch()

if __name__ == '__main__':
  main(sys.argv)
