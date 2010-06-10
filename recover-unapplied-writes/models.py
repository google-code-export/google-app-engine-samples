# Sample models for applying unapplied writes.
from google.appengine.ext import db

class Kitten(db.Model):
  # Key name is the kitten name.
  color = db.StringProperty()
  weight = db.IntegerProperty()


class __unapplied_write__Kitten(db.Expando):
  pass

