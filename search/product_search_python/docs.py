#!/usr/bin/env python
#
# Copyright 2012 Google Inc.
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

""" Contains 'helper' classes for managing search.Documents.
BaseDocumentManager provides some common utilities, and the Product subclass
adds some Product-document-specific helper methods.
"""

import collections
import copy
import logging
import re
import string
import urllib

import categories
import config
import errors
import models

from google.appengine.api import search
from google.appengine.ext import ndb


class BaseDocumentManager(object):
  """Abstract class. Provides helper methods to manage search.Documents."""

  _INDEX_NAME = None
  _VISIBLE_PRINTABLE_ASCII = frozenset(
    set(string.printable) - set(string.whitespace))

  def __init__(self, doc):
    """Builds a dict of the fields mapped against the field names, for
    efficient access.
    """
    self.doc = doc
    fields = doc.fields
    self.doc_map = {}
    for field in fields:
      fieldlist = self.doc_map.get(field.name,[])
      fieldlist.append(field)
      self.doc_map[field.name] = fieldlist

  def getFirstFieldVal(self, fname):
    """Get the value of the (first) document field with the given name."""
    try:
      return self.doc_map.get(fname)[0].value
    except IndexError:
      return None
    except TypeError:
      return None

  def setFirstField(self, new_field):
    """Set the value of the (first) document field with the given name."""
    for i, field in enumerate(self.doc.fields):
      if field.name == new_field.name:
        self.doc.fields[i] = new_field
        return True
    return False

  @classmethod
  def isValidDocId(cls, doc_id):
    """Checks if the given id is a visible printable ASCII string not starting
    with '!'.  Whitespace characters are excluded.
    """
    for char in doc_id:
      if char not in cls._VISIBLE_PRINTABLE_ASCII:
        return False
    return not doc_id.startswith('!')

  @classmethod
  def getIndex(cls):
    return search.Index(name=cls._INDEX_NAME)

  @classmethod
  def deleteAllInIndex(cls):
    """Delete all the docs in the given index."""
    docindex = cls.getIndex()

    try:
      while True:
        # until no more documents, get a list of documents,
        # constraining the returned objects to contain only the doc ids,
        # extract the doc ids, and delete the docs.
        document_ids = [document.doc_id
                        for document in docindex.list_documents(ids_only=True)]
        if not document_ids:
          break
        docindex.remove(document_ids)
    except search.Error:
      logging.exception("Error removing documents:")

  @classmethod
  def getDoc(cls, doc_id):
    """Return the document with the given doc id. One way to do this is via
    the list_documents method, as shown here.  If the doc id is not in the
    index, the first doc in the list will be returned instead, so we need
    to check for that case."""
    if not doc_id:
      return None
    try:
      index = cls.getIndex()
      response = index.list_documents(
          start_doc_id=doc_id, limit=1, include_start_doc=True)
      if response.results and response.results[0].doc_id == doc_id:
        return response.results[0]
      return None
    except search.InvalidRequest: # catches ill-formed doc ids
      return None

  @classmethod
  def removeDocById(cls, doc_id):
    """Remove the doc with the given doc id."""
    try:
      cls.getIndex().remove(doc_id)
    except search.Error:
      logging.exception("Error removing doc id %s.", doc_id)

  @classmethod
  def add(cls, documents):
    """wrapper for search index add method; specifies the index name."""
    try:
      return cls.getIndex().add(documents)
    except search.Error:
      logging.exception("Error adding documents.")


class Product(BaseDocumentManager):
  """Provides helper methods to manage Product documents.  All Product documents
  built using these methods will include a core set of fields (see the
  _buildCoreProductFields method).  We use the given product id (the Product
  entity key) as the doc_id.  This is not required for the entity/document
  design-- each explicitly point to each other, allowing their ids to be
  decoupled-- but using the product id as the doc id allows a document to be
  reindexed given its product info, without having to fetch the
  existing document."""

  _INDEX_NAME = config.PRODUCT_INDEX_NAME

  # 'core' product document field names
  PID = 'pid'
  DESCRIPTION = 'description'
  CAT = 'cat'
  CATNAME = 'catname'
  PNAME = 'name'
  PRICE = 'price'
  AR = 'ar' #average rating

  _SORT_OPTIONS = [
        [AR, 'average rating', search.SortExpression(
            expression=AR,
            direction=search.SortExpression.DESCENDING, default_value=1)],
        [PRICE, 'price', search.SortExpression(
            expression=PRICE,
            direction=search.SortExpression.ASCENDING, default_value=1)],
        [CATNAME, 'category', search.SortExpression(
            expression=CATNAME,
            direction=search.SortExpression.ASCENDING, default_value='')],
        [PNAME, 'product name', search.SortExpression(
            expression=PNAME,
            direction=search.SortExpression.ASCENDING, default_value='')]
      ]

  _SORT_MENU = None
  _SORT_DICT = None


  @classmethod
  def deleteAllInProductIndex(cls):
    cls.deleteAllInIndex()

  @classmethod
  def getSortMenu(cls):
    if not cls._SORT_MENU:
      cls._buildSortMenu()
    return cls._SORT_MENU

  @classmethod
  def getSortDict(cls):
    if not cls._SORT_DICT:
      cls._buildSortDict()
    return cls._SORT_DICT

  @classmethod
  def _buildSortMenu(cls):
    """Build the default set of sort options used for Product search.
    Of these options, all but 'relevance' reference core fields that
    all Products will have."""
    res = [(elt[0], elt[1]) for elt in cls._SORT_OPTIONS]
    cls._SORT_MENU = [('relevance', 'relevance')] + res

  @classmethod
  def _buildSortDict(cls):
    """Build a dict that maps sort option keywords to their corresponding
    SortExpressions."""
    cls._SORT_DICT = {}
    for elt in cls._SORT_OPTIONS:
      cls._SORT_DICT[elt[0]] = elt[2]

  @classmethod
  def getDocFromPid(cls, pid):
    """Given a pid, get its doc. We're using the pid as the doc id, so we can
    do this via a direct fetch."""
    return cls.getDoc(pid)

  @classmethod
  def removeProductDocByPid(cls, pid):
    """Given a doc's pid, remove the doc matching it from the product
    index."""
    cls.removeDocById(pid)

  @classmethod
  def updateRatingInDoc(cls, doc_id, avg_rating):
    # get the associated doc from the doc id in the product entity
    doc = cls.getDoc(doc_id)
    if doc:
      pdoc = cls(doc)
      cat = pdoc.getCategory()
      # The category cast to int is to avoid a current dev appserver issue when
      # reindexing. Not an issue for a deployed app.
      pdoc.setCategory(int(cat))
      pdoc.setAvgRating(avg_rating)
      # The use of the same id will cause the existing doc to be reindexed.
      return doc
    else:
      raise errors.OperationFailedError(
          'Could not retrieve doc associated with id %s' % (doc_id,))

  @classmethod
  def updateRatingsInfo(cls, doc_id, avg_rating):
    """Given a models.Product entity, update and reindex the associated
    document with the product entity's current average rating. """

    ndoc = cls.updateRatingInDoc(doc_id, avg_rating)
    # reindex the returned updated doc
    return cls.add(ndoc)

# 'accessor' methods

  def getPID(self):
    """Get the value of the 'pid' field of a Product doc."""
    return self.getFirstFieldVal(self.PID)

  def getName(self):
    """Get the value of the 'name' field of a Product doc."""
    return self.getFirstFieldVal(self.PNAME)

  def getDescription(self):
    """Get the value of the 'description' field of a Product doc."""
    return self.getFirstFieldVal(self.DESCRIPTION)

  def getCategory(self):
    """Get the value of the 'cat' field of a Product doc."""
    return self.getFirstFieldVal(self.CAT)

  def getCategoryName(self):
    """Get the value of the 'catname' field of a Product doc."""
    return self.getFirstFieldVal(self.CATNAME)

  def setCategory(self, cat):
    """Set the value of the 'cat' (category) field of a Product doc."""
    return self.setFirstField(search.NumberField(name=self.CAT, value=cat))

  def getAvgRating(self):
    """Get the value of the 'ar' (average rating) field of a Product doc."""
    return self.getFirstFieldVal(self.AR)

  def setAvgRating(self, ar):
    """Set the value of the 'ar' field of a Product doc."""
    return self.setFirstField(search.NumberField(name=self.AR, value=ar))

  def getPrice(self):
    """Get the value of the 'price' field of a Product doc."""
    return self.getFirstFieldVal(self.PRICE)

  @classmethod
  def generateRatingsBuckets(cls, query_string):
    """Builds a dict of ratings 'buckets' and their counts, based on the
    value of the 'avg_rating" field for the documents retrieved by the given
    query.  See the 'generateRatingsLinks' method.  This information will
    be used to generate sidebar links that allow the user to drill down in query
    results based on rating.

    For demonstration purposes only; this will be expensive for large data
    sets.
    """

    # do the query on the *full* search results
    # to generate the facet information, imitating what may in future be
    # provided by the FTS API.
    try:
      sq = search.Query(
          query_string=query_string.strip())
      search_results = cls.getIndex().search(sq)
    except search.Error:
      logging.exception('An error occurred on search.')
      return None

    ratings_buckets = collections.defaultdict(int)
    # populate the buckets
    for res in search_results:
      ratings_buckets[int((cls(res)).getAvgRating() or 0)] += 1
    return ratings_buckets

  @classmethod
  def generateRatingsLinks(cls, query, phash):
    """Given a dict of ratings 'buckets' and their counts,
    builds a list of html snippets, to be displayed in the sidebar when
    showing results of a query. Each is a link that runs the query, additionally
    filtered by the indicated ratings interval."""

    ratings_buckets = cls.generateRatingsBuckets(query)
    if not ratings_buckets:
      return None
    rlist = []
    for k in range(config.RATING_MIN, config.RATING_MAX+1):
      try:
        v = ratings_buckets[k]
      except KeyError:
        return
      # build html
      if k < 5:
        htext = '%s-%s (%s)' % (k, k+1, v)
      else:
        htext = '%s (%s)' % (k, v)
      phash['rating'] = k
      hlink = '/psearch?' + urllib.urlencode(phash)
      rlist.append((hlink, htext))
    return rlist

  @classmethod
  def _buildCoreProductFields(
      cls, pid, name, description, category, category_name, price):
    """Construct a 'core' document field list for the fields common to all
    Products. The various categories (as defined in the file 'categories.py'),
    may add additional specialized fields; these will be appended to this
    core list. (see _buildProductFields)."""
    fields = [search.TextField(name=cls.PID, value=pid),
              search.TextField(name=cls.PNAME, value=name),
              # strip the markup from the description value, which can
              # potentially come from user input.  We do this so that
              # we don't need to sanitize the description in the
              # templates, showing off the Search API's ability to mark up query
              # terms in generated snippets.  This is done only for
              # demonstration purposes; in an actual app,
              # it would be preferrable to use a library like Beautiful Soup
              # instead.
              # We'll let the templating library escape all other rendered
              # values for us, so this is the only field we do this for.
              search.TextField(
                  name=cls.DESCRIPTION,
                  value=re.sub(r'<[^>]*?>', '', description)),
              search.NumberField(name=cls.CAT, value=category),
              search.TextField(name=cls.CATNAME, value=category_name),
              search.NumberField(name=cls.AR, value=0.0),
              search.NumberField(name=cls.PRICE, value=price)
             ]
    return fields

  @classmethod
  def _buildProductFields(cls, pid=None, category=None, name=None,
      description=None, category_name=None, price=None, **params):
    """Build all the additional non-core fields for a document of the given
    product type (category), using the given params dict, and the
    already-constructed list of 'core' fields.  All such additional
    category-specific fields are treated as required.
    """

    fields = cls._buildCoreProductFields(
        pid, name, description, category, category_name, price)
    # get the specification of additional (non-'core') fields for this category
    pdict = categories.product_dict.get(category_name)
    if pdict:
      # for all fields
      for k, field_type in pdict.iteritems():
        # see if there is a value in the given params for that field.
        # if there is, get the field type, create the field, and append to the
        # document field list.
        if k in params:
          v = params[k]
          if field_type == search.NumberField:
            try:
              val = float(v)
              fields.append(search.NumberField(name=k, value=val))
            except ValueError:
              error_message = ('bad value %s for field %s of type %s' %
                               (k, v, field_type))
              logging.error(error_message)
              raise errors.OperationFailedError(error_message)
          elif field_type == search.TextField:
            fields.append(search.TextField(name=k, value=str(v)))
          else:
            # TODO -- add handling of other field types for generality.  Not
            # needed for our current sample data.
            logging.warn('not processed: %s, %s, of type %s', k, v, field_type)
        else:
          error_message = ('value not given for field "%s" of field type "%s"'
                           % (k, field_type))
          logging.warn(error_message)
          raise errors.OperationFailedError(error_message)
    else:
      # else, did not have an entry in the params dict for the given field.
      logging.warn(
          'product field information not found for category name %s',
          params['category_name'])
    return fields

  @classmethod
  def _createDocument(
      cls, pid=None, category=None, name=None, description=None,
      category_name=None, price=None, **params):
    """Create a Document object from given params."""
    # check for the fields that are always required.
    if pid and category and name:
      # First, check that the given pid has only visible ascii characters,
      # and does not contain whitespace.  The pid will be used as the doc_id,
      # which has these requirements.
      if not cls.isValidDocId(pid):
        raise errors.OperationFailedError("Illegal pid %s" % pid)
      # construct the document fields from the params
      resfields = cls._buildProductFields(
          pid=pid, category=category, name=name,
          description=description,
          category_name=category_name, price=price, **params)
      # build and index the document.  Use the pid (product id) as the doc id.
      # (If we did not do this, and left the doc_id unspecified, an id would be
      # auto-generated.)
      d = search.Document(doc_id=pid, fields=resfields)
      return d
    else:
      raise errors.OperationFailedError('Missing parameter.')

  @classmethod
  def _normalizeParams(cls, params):
    """Normalize the submitted params for building a product."""

    params = copy.deepcopy(params)
    chash = models.Category.getCategoryDict()
    try:
      params['pid'] = params['pid'].strip()
      params['name'] = params['name'].strip()
      params['category_name'] = params['category']
      params['category'] = int(chash.get(params['category']))
      try:
        params['price'] = float(params['price'])
      except ValueError:
        error_message = 'bad price value: %s' % params['price']
        logging.error(error_message)
        raise errors.OperationFailedError(error_message)
      return params
    except KeyError as e1:
      raise errors.OperationFailedError(e1)
    except errors.Error as e2:
      logging.debug(
          'Problem with params: %s: %s' % (params, e2.error_message))
      raise errors.OperationFailedError(e2.error_message)

  @classmethod
  def buildProductBatch(cls, rows):
    """Build product documents and their related datastore entities, in batch,
    given a list of params dicts.  Should be used for new products, as does not
    handle updates of existing product entities."""

    docs = []
    dbps = []
    for row in rows:
      try:
        params = cls._normalizeParams(row)
        doc = cls._createDocument(**params)
        docs.append(doc)
        # create product entity, sans doc_id
        dbp = models.Product(
            id=params['pid'], price=params['price'],
            category=params['category'])
        dbps.append(dbp)
      except errors.OperationFailedError:
        logging.error('error creating document from data: %s', row)
    doc_ids = cls.add(docs)
    if len(doc_ids) != len(dbps):
      raise errors.OperationFailedError(
          'Error: wrong number of doc ids returned from indexing operation')
    # now set the entities with the doc ids, the list of which are returned in
    # the same order as the list of docs given to the indexers
    for i, dbp in enumerate(dbps):
      dbp.doc_id = doc_ids[i].document_id
    # persist the entities
    ndb.put_multi(dbps)

  @classmethod
  def buildProduct(cls, params):
    """Create/update a product document and its related datastore entity.  The
    product id and the field values are taken from the params dict.
    """
    params = cls._normalizeParams(params)
    # check to see if doc already exists
    curr_doc = cls.getDocFromPid(params['pid'])
    d = cls._createDocument(**params)
    if curr_doc:  #don't overwrite ratings info from existing doc
      avg_rating = cls(curr_doc).getAvgRating()
      cls(d).setAvgRating(avg_rating)

    # This will reindex if a doc with that doc id already exists
    doc_ids = cls.add(d)
    try:
      doc_id = doc_ids[0].document_id
    except IndexError:
      doc_id = None
      raise errors.OperationFailedError('could not index document')
    logging.debug('got new doc id %s for product: %s', doc_id, params['pid'])

    # now update the entity
    def _tx():
      # Check whether the product entity exists. If so, we want to update
      # from the params, but preserve its ratings-related info.
      prod = models.Product.get_by_id(params['pid'])
      if prod:  #update
        prod.update_core(params, doc_id)
      else:   # create new entity
        prod = models.Product.create(params, doc_id)
      prod.put()
      return prod
    prod = ndb.transaction(_tx)
    logging.debug('prod: %s', prod)
    return prod
