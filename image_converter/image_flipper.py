#!/usr/bin/python2.4
#
# Copyright 2010 Google Inc. All Rights Reserved.
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

"""Demo for Appengine and pull taskqueue integration with TaskPuller.

This example shows how Google AppEngine apps can use PULL queues and add
tasks to get part of work/processing done outside appengine environment.
This lets the app-engine user use any executable binary (like OCR reader)
and thus complements the Google AppEngine with processing on an external
machine. This demonstrates end-to-end integration of a Google AppEngine app
with gtaskqueue_puller(running on VMs) by putting a task in the taskqueue to
flip the image by the app, this task gets processed(fliping of image) by the
taskqueue puller workers and output from the app is posted back to the same app.
This app handles the posted data and stores the flipped image in datastore.
The images are searchable by name and user can see both uploaded as well as
processed/flipped image. In addition the handler that the workers use to post
data back to AppEngine are OAuth1 protected, and limited to admins of the
AppEngine application.

Example puller command line to acces pull Queue tasks using the REST API on
a worker outside AppEngine:

  gtaskqueue_puller --project_name=imageconvertdemo \
  --taskqueue_name=imageconvert --lease_secs=30
  --executable_binary="convert -annotate 30x20+10+10 google.rocks"
  --output_url="http://imageconvertdemo.appspot.com/taskdata?name="
  --appengine_access_token_file=./access_token

"""

__author__ = 'vibhooti@google.com (Vibhooti Verma)'

import logging
from google.appengine.api import oauth
from google.appengine.ext import db
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import webapp
from google.appengine.api import taskqueue


class SmallImage(db.Model):
  """Stores image in datastore."""
  image_name = db.StringProperty(required = True)
  image = db.BlobProperty(required = True)


class TaskImageMap(db.Model):
  """Stores task_id to image_name mapping."""
  image_ref = db.ReferenceProperty(SmallImage)
  task_name = db.StringProperty(required = True)


class ImageRequestHandler(webapp.RequestHandler):
  """Handles requests to upload an image."""

  def get(self):
    """Get to let the user upload any image."""
    self.response.out.write('''
    <html>
      <body>
        <form action="/" method="post" enctype="multipart/form-data">
          <p>Name: <input type="text" name="name" /></p>
          <div><input type="file" name="upload1"></div>
          <div><input type="submit" value="Upload"></div>
        </form>
      </body>
    </html>
    ''')

  def WriteEntry(self, image_name, value):
    """Stores the image in data store as a blob object."""
    small_image = SmallImage(key_name=image_name,
                             image_name=image_name,
                             image=db.Blob(value))
    small_image.put()
    self.EnqueueTask(small_image, value)

  def EnqueueTask(self, image_ref, value):
    """Enqueues the task in pull queue to process the image.

    Args:
     key: Name of the image
     value: Image to be sent as payload

    This function sets the uploaded image as payload of the task and then puts
    the task in appropriate queue (defined in queue.yaml). Project name gets
    set automatically as project in which your app is running. task_id gets
    automatically generated if you do not sepcify explicitely. After we put the
    task in the queue, we also store the task_id to image name mapping which
    can be used later when output of the task is posted back.
    """
    # queuename must be specified in queue.yaml
    q = taskqueue.Queue('imageconvert')
    task = taskqueue.Task(payload=value, method='PULL')
    q.add(task)
    # create a taskid to image_name entry and put it in the datastore
    task_image_entry = TaskImageMap(key_name=task.name,
                                    task_name=task.name,
                                    image_ref=image_ref)
    task_image_entry.put()

  def post(self):
    """Stores the user-uploaded image in datastore and enqueues a task in pull
    queue to process it.
    """
    name = self.request.get('name')
    for arg in self.request.arguments():
      if arg.startswith('upload'):
        image_contents = self.request.get(arg)
        if len(image_contents) > 0:
          self.WriteEntry(name, image_contents)
          self.redirect('/imagestatus?name=' + name)
          break


class TaskDataHandler(webapp.RequestHandler):
  """Handles the output of tasks posted from taskpuller client.

  This is responsible for handling the data/output posted from the taskpuller
  client. Taskpuller client essentially has a pool of workers to pull
  tasks(enqueud by your app) from pull-taskqueues. A worker enqueues a
  task, does the desired processing on payload of the task and posts the data
  back to your application. This is the handler which handles this output and
  takes appropriate action. For example in this app, taskpuller post the image
  after processing(flipping) it and we store the processed image in datastore
  with original image-name appended with _processed.
  """

  def GetImageNameFromTaskImageMap(self, key):
    """Returns corresponding image_name for the taskid."""
    task_image_entry = TaskImageMap.get_by_key_name(key)
    if task_image_entry:
      return task_image_entry.image_ref.image_name
    else:
      return None

  def post(self):
    """Handles the output posted from taskqueue puller.

    name is a queryparam that is the task_id of the task whose output is being
    posted by the puller. We first find the image_name for the task and store
    the processed image as image_name_processed. This helps when user searches
    for the image and we can show both uploaded as well as processed image.
    This handler is OAuth enabled, so that only the administrators of this app
    can call this handler using an OAuth token.
    """

    try:
      user = oauth.get_current_user()
      # Currently there is no way to figure out if a given OAuth user is an
      # admin. users.is_current_user_admin() only takes care of logged in users,
      # not users who are presenting tokens on OAuth. We should fix this!
      if user and user.nickname() == 'svivek@google.com':
        task_name = self.request.get('name')
        name = self.GetImageNameFromTaskImageMap(task_name)
        if name:
          image_key = name + '_processed'
          image_contents = self.request.body
          small_image = SmallImage(key_name=image_key,
                                   image_name=image_key,
                                   image=db.Blob(image_contents))
          small_image.put()
        else:
          logging.error('No image associated with this task')
          self.error(404)
      else:
        logging.error('unauthorized user ' + user.nickname())
        self.error(403)
    except oauth.OAuthRequestError, e:
      logging.error('no oauth token detected')
      self.error(403)


class ImageServer(webapp.RequestHandler):
  """Serves image from datastore."""

  def get(self):
    """Get to show the image"""
    name = self.request.get('name')
    small_image = SmallImage.get_by_key_name(name)
    if small_image and small_image.image:
      self.response.headers['Content-Type'] = 'image/jpeg'
      self.response.out.write(small_image.image)
      logging.info('returned %d bytes' % len(small_image.image))
    else:
      self.error(404)


class ImageStatusHandler(webapp.RequestHandler):
  """Lets user search by image name and shows both uploaded and processed
  image."""

  def ImageExists(self, key):
    small_image = SmallImage.get_by_key_name(key)
    return small_image is not None

  def get(self):
    name = self.request.get('name')
    logging.info('name is ' + name)
    if self.ImageExists(name):
      uploaded_url = '/images?name=' + name
      processed_url = '/images?name=' + name +'_processed'
      uploaded_url_str = '<img src=\"' + uploaded_url + '\" ></img> <br>'
      if self.ImageExists(name +"_processed"):
        processed_url_str = '<img src=\"' + processed_url + \
                            '\" >' + '</img> <br>'
      else:
        processed_url_str = 'Image is being processed, it will be eventaully\
        available at ' + '<a href=\"' + processed_url + '\" >' + 'here'\
        + '</a> <br>'
    else:
      self.response.out.write('No Image Uploaded named ' + name + '. Please Try\
                              again!')
      return None

    self.response.out.write('''
                               <html>
                                 <body> ''')

    self.response.out.write('''
                            <TABLE>
                            <CAPTION>Image Status for image %s</CAPTION>
                            <TR>
                            <TD>Uploaded Image : <TD> ''' % name)
    self.response.out.write(uploaded_url_str)
    self.response.out.write(''' <TR>
                            <TD> Processed Image : <TD> ''')
    self.response.out.write(processed_url_str)
    self.response.out.write(''' </TD>
                            </TABLE>''')
    self.response.out.write('''
      </body>
    </html>
    ''')


class SearchHandler(webapp.RequestHandler):
  def get(self):
    """Searches image by the name given during upload."""
    self.response.out.write('''
    <html>
      <body>
        <form action="/search" method="post" enctype="multipart/form-data">
          <p>Image: <input type="text" name="name" /></p>
          <div><input type="submit" value="Search"></div>
        </form>
      </body>
    </html>
    ''')

  def post(self):
    """Searches and shows both uploaded image and processed image. If task has
    notfinished yet, it shows the  tentative URL where the processed iamge will
    be available after task finishes."""
    name = self.request.get('name')
    self.redirect('/imagestatus?name=' + name)


def main():
  application = webapp.WSGIApplication(
      [('/', ImageRequestHandler),
       ('/search', SearchHandler),
       ('/imagestatus', ImageStatusHandler),
       ('/images', ImageServer),
       ('/taskdata', TaskDataHandler),
      ],
      debug=True)

  run_wsgi_app(application)

if __name__ == '__main__':
  main()
