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

import datetime
import os
import time
import wsgiref.handlers
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from models import Channel
from models import Log


class FixedOffsetZone(datetime.tzinfo):
  def __init__(self, offset_hours):
    self._offset = datetime.timedelta(hours=offset_hours)

  def utcoffset(self, dt):
    return self._offset

  def dst(self, dt):
    return datetime.timedelta(0)


class QueryController(webapp.RequestHandler):
  """Controller that handles the query pages."""

  _MAX_CHANNELS = 20  # maximum to show on Channels page
  _TRANSCRIPT_LINES = 100

  def Render(self, template_file, values):
    path = os.path.join(os.curdir, '..', 'templates', template_file)
    self.response.out.write(template.render(path, values))

  def RenderTranscript(self):
    channel = self.request.get('channel', '')
    values = {
        'channel': channel,
    }

    # Query for the correct set of logs.
    query = Log.all().filter('channel =', channel)
    if 'start_time' in self.request.GET:
      # Followed a 'next page' link
      query.order('timestamp')
      t = time.strptime(self.request.GET['start_time'], '%Y%m%d%H%M%S')
      query.filter('timestamp >=', datetime.datetime(*t[0:6]))
      # Fetch N+1 to check for a next page
      logs = query.fetch(self._TRANSCRIPT_LINES + 1)
      values['first_time'] = logs[0].timestamp.strftime('%Y%m%d%H%M%S')
      if len(logs) > self._TRANSCRIPT_LINES:
        logs = logs[0:self._TRANSCRIPT_LINES]
        values['last_time'] = logs[-1].timestamp.strftime('%Y%m%d%H%M%S')
    else:
      query.order('-timestamp')
      reversed = True
      if 'end_time' in self.request.GET:
        # Followed a 'prev page' link
        t = time.strptime(self.request.GET['end_time'], '%Y%m%d%H%M%S')
        t = list(t[0:6])
        t[5] += 1  # round up so we ignore fractional seconds
        query.filter('timestamp <=', datetime.datetime(*t))
        # Fetch N+1 to check for a prev page
        logs = query.fetch(self._TRANSCRIPT_LINES + 1)
        values['last_time'] = logs[0].timestamp.strftime('%Y%m%d%H%M%S')
      else:
        # No 'prev/next' links followed, so no filter
        # Fetch N+1 to check for a prev page
        logs = query.fetch(self._TRANSCRIPT_LINES + 1)
      if len(logs) > self._TRANSCRIPT_LINES:
        logs = logs[0:self._TRANSCRIPT_LINES]
      values['first_time'] = logs[-1].timestamp.strftime('%Y%m%d%H%M%S')
      logs.reverse()
    values['logs'] = logs

    # Adjust timezone if requested.
    if 'tz' in self.request.GET:
      tz = FixedOffsetZone(int(self.request.get('tz')))
      for log in logs:
        t = log.timestamp + tz.utcoffset(log.timestamp)
        log.timestamp = t.replace(tzinfo=tz)

    self.Render('transcript.html', values)

  def get(self, op):
    if op == 'channels':
      channels = Channel.all().order('-num_members').fetch(self._MAX_CHANNELS)
      self.Render('channels.html', {
          'channels': channels,
          'max': min(len(channels), self._MAX_CHANNELS),
      })
    elif op == 'transcript':
      self.RenderTranscript()


def main():
  app = webapp.WSGIApplication([
      ('/transcript/(channels|transcript)', QueryController),
  ], debug=True)
  wsgiref.handlers.CGIHandler().run(app)


if __name__ == '__main__':
  main()
