#!/usr/bin/env python

import datetime
import hashlib
import os
import wsgiref.handlers

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext.webapp.util import login_required

import pickle
import base64
import logging
from time import mktime

def encodebookmark(created, key):
  timestamp = mktime(created.timetuple())+1e-6*created.microsecond
  return base64.b64encode("%f|%s" % (timestamp, key))

def decodebookmark(b64bookmark):
  timestamp, key = base64.b64decode(b64bookmark).split('|')
  created = datetime.datetime.fromtimestamp(float(timestamp))
  return created, key


class Suggestion2(db.Model):
  suggestion = db.StringProperty()
  created = db.DateTimeProperty(auto_now_add=True)  
  
PAGESIZE = 5  

class Suggestion2Handler(webapp.RequestHandler):

  def get(self):
    offset = self.request.get('offset')
    next = None
    if offset:
      created, key = decodebookmark(offset)
      logging.info("key = %s, created = %s" % (key, created))
      suggestions = Suggestion2.gql(" WHERE created = :created AND __key__ >= :key ORDER BY __key__ ASC", created = created, key = db.Key(key)).fetch(PAGESIZE+1) 
      logging.info(type(suggestions))
      if len(suggestions) < (PAGESIZE + 1):
        logging.info("Going for more, only got %d" % len(suggestions))
        remainder = PAGESIZE + 1 - len(suggestions)
        moresuggestions = Suggestion2.gql('WHERE created < :created ORDER BY created DESC, __key__ ASC', created = created).fetch(remainder)
        logging.info("Got %d more" % len(moresuggestions))
        suggestions += moresuggestions
        logging.info("Total %d" % len(suggestions))
    else:
      suggestions = Suggestion2.gql("ORDER BY created DESC, __key__ ASC").fetch(PAGESIZE+1)
    if len(suggestions) == PAGESIZE+1:
      next = encodebookmark(suggestions[-1].created, suggestions[-1].key())
      suggestions = suggestions[:PAGESIZE]
      
    template_values = {'next': next, 'suggestions': suggestions}    
    template_file = os.path.join(os.path.dirname(__file__), 'suggestion.html')
    self.response.out.write(template.render(template_file, template_values))

  def post(self):
    s = Suggestion2(suggestion = self.request.get('suggestion'))        
    s.put()
    self.redirect('/key/')
    
class Suggestion2Populate(webapp.RequestHandler):
  def post(self):
    now = datetime.datetime.now()
    for i in range(6):
      s = Suggestion2(suggestion = "Suggestion %d" % i, created = now)
      s.put()
    self.redirect('/key/')
        

def main():
  application = webapp.WSGIApplication([
    ('/key/pop/', Suggestion2Populate),
    ('/key/', Suggestion2Handler)
  ], debug=True)
  wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()
  

