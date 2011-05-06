#!/usr/bin/python2.4
#
# Copyright (C) 2011 Google Inc.
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

"""An very simple app using pull queues to tally votes."""

__author__ = 'nverne@google.com (Nicholas Verne)'

import os
import time

from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

LANGUAGES = ['Java', 'Go', 'C++', 'Perl', 'Python']

class Tally(db.Model):
  """Simple counting model."""
  count = db.IntegerProperty(default=0, required=True)

  @classmethod
  def increment_by(cls, key_name, count):
    """Increases a Tally's count. Should be run in a transaction."""
    tally = cls.get_by_key_name(key_name)
    if tally is None:
      tally = cls(key_name=key_name)
    tally.count += count
    tally.put()


class VoteHandler(webapp.RequestHandler):
  """Handles adding of vote tasks."""

  def get(self):
    """Displays the voting form."""
    self.render_template('index.html', {'tallies': self.get_tallies(),
                                        'LANGUAGES': LANGUAGES})

  def post(self):
    """Adds tasks to votes queue if ugliest is valid."""
    ugliest = self.request.get('ugliest')

    if ugliest and ugliest in LANGUAGES:
      q = taskqueue.Queue('votes')
      q.add(taskqueue.Task(payload=ugliest, method='PULL'))
    self.redirect('/')

  def get_tallies(self):
    """Fetches tallies from memcache if possible, otherwise from datastore."""
    tallies = memcache.get('tallies')
    if tallies is None:
      tallies = Tally.all().fetch(len(LANGUAGES))
      memcache.set('tallies', tallies, time=5)
    return tallies

  def render_template(self, name, template_args):
    """Renders a named django template."""
    path = os.path.join(os.path.dirname(__file__), 'templates', name)
    self.response.out.write(template.render(path, template_args))


class TallyHandler(webapp.RequestHandler):
  """Pulls tasks from the vote queue."""

  def store_tallies(self, tallies):
    """Updates the tallies in datastore."""
    for key_name, count in tallies.iteritems():
      db.run_in_transaction(Tally.increment_by, key_name, count)

  def post(self):
    """Leases vote tasks, accumulates tallies and stores them."""
    q = taskqueue.Queue('votes')
    # Keep leasing tasks in a loop. When the task fails due to
    # deadline, it should be retried.
    while True:
      tasks = q.lease_tasks(300, 1000)
      if not tasks:
        # Let the retry parameters of the queue cause this
        # task to be rescheduled.
        self.error(500)
        return

      tallies = {}
      # accumulate tallies in memory
      for t in tasks:
        tallies[t.payload] = tallies.get(t.payload, 0) + 1

      self.store_tallies(tallies)
      q.delete_tasks(tasks)

class StartHandler(webapp.RequestHandler):
  """Starts some tally tasks."""
  def get(self):
    workers = int(self.request.get('workers', 2))
    q = taskqueue.Queue('tally')
    q.purge()
    time.sleep(2)

    if workers > 0:
      q.add([taskqueue.Task(url='/tally',
                            countdown=x) for x in xrange(workers)])
    self.redirect('/')

application = webapp.WSGIApplication([
    ('/', VoteHandler),
    ('/tally', TallyHandler),
    ('/start', StartHandler),
    ], debug=True)


def main():
  run_wsgi_app(application)

if __name__ == '__main__':
  main()
