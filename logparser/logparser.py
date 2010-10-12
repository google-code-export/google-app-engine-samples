#!/usr/bin/python2.5
#
# Copyright 2010 Google Inc.
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
#

"""Tool to parse appcfg request_logs to a sqlite database for further analysis.

Example:

  # Download request logs (with applogs) into requests.txt
  appcfg.py request_logs --severity 0 --include_all <appdirectory> requests.txt
  # Run the logparser to insert them into requests.db.
  # (You can specify multiple input files.)
  logparser.py --db requests.db requests.txt
  # Query them using the sqlite3 interactive command line interface.
  sqlite3 requests.db
  sqlite> -- what are the most common 404s?
  sqlite> select distinct request_line, count(*) from requests
     ...> where status == 404 group by request_line order by request_line desc;
  sqlite> -- what requests see 'Deadline Exceeded'?
  sqlite> select distinct request_line from requests
     ...> where applog like '%DeadlineExceeded%';
  sqlite> -- How many loading requests were seen?
  sqlite> select count(*) from requests where loading_request=1;
  sqlite> -- What was the average cpm across all pages?
  sqlite> select sum(cpm_usd)/count(cpm_usd) from requests;


Contents of the Database Table:

  The database contains request logs parsed from the downloaded log. That log
  contains an Apache Combined Log Format* lines followed by zero or more
  tab-indented logging statements from the application.

  The default format of the request line is
   "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-agent}i\""

  If you specify --include_vhost or --include_all, it becomes
   "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-agent}i\" \"%v\""

  If you add --include_all, it is the same as above plus zero or more
  of the following tags:
   ms (elapsed request time)
   cpu_ms
   api_cpu_ms
   cpm_usd (float)
   queue_name (task queue name)
   task_name (task queue task name)
   loading_request=1 (if this is a loading request)
   pending_ms (time in pending queue)
   exit_code=int
   throttle_code=int

  These are recorded in a sqlite database in a table 'requests', which
  has the following columns: (Source noted in parentheses.)
   remotehost (%h)
   user (%u)
   request_time_str (%t)
   request_line (%r)
   status (%s)
   bytes (%b)
   referer (%{Referer}i)
   useragent (%{User-agent}i)
   host (%v)
   ms
   cpu_ms
   api_cpu_ms
   cpm_usd
   queue_name
   task_name
   loading_request
   pending_ms
   exit_code
   throttle_code

  TODO: Parse method, path, querystring, and protocol from request_line.

  The additional logging lines are combined into the following columns:
  applog, applog0, applog1, applog2, applog3, applog4
  The first (applog) combines all severity levels; the others include only that
  one severity level to allow for precise queries.

  * http://httpd.apache.org/docs/1.3/mod/mod_log_config.html#formats
  The above format is the particular format one which App Engine outputs. This
  log parser is not a general parser.


Custom Columns:

  You can also specify regular expressions over an applog to create
  one or more custom columns.

  Example:

    --custom_column "widgets:^1:[0-9.]+ Found ([0-9]+) widgets"

  This will locate all Info logs (severity 1) which look like this:

    1:1286325423.286856 Found 12 widgets

  and pull out the "12" part. Now you can run a query like these:

  sqlite> -- How many widgets were seen?
  sqlite> select select sum(widgets) from requests;
  sqlite> -- What was the approximate the processing time per widget?
  sqlite> select sum(cpu_ms)/cast(sum(widgets) as float)
     ...> from requests where widgets > '';

  You can specify multiple --custom_column flags.


Handling Duplicate Items:

  If --discard_duplicates is specified, the entire request log line is stored
  in "request_log", as primary key. This allows you to run this tool multiple
  times over several files to combine them--it'll only record the first one
  seen. However, you may lose legitimate duplicate records; adding --include_all
  will reduce the chance of legitimate duplicates occuring.

  This is particularly useful as request_logs has no mechanism to download
  all request logs and app logs items at once. A common pattern might be:

  # Download all applogs.
  appcfg.py request_logs --severity 0 --include_all <appdirectory> applogs.txt
  # Download all requestlogs. There may be overlap with the applogs.
  appcfg.py request_logs --include_all <appdirectory> request.txt
  # Run the logparser to insert them into requests.db.
  logparser.py --discard_duplicates --db requests.db requests.txt applogs.txt
"""
# pylint: disable-msg=C6409

import logging
import optparse
import re
import sys
import sqlite3


class Error(Exception):
  """Base logparser error type."""


class LineParsingFailure(Error):
  """Cannot parse the line."""


def create_database(db_filename, discard_duplicates, custom_columns):
  """Create a connection to the database, create needed tables.

  Args:
    db_filename: Path to the db file.
    discard_duplicates: If it should attempt to discard duplicate log lines.
    custom_columns: Dictionary, column name: regexp.

  Returns:
    Sqlite database connection, with tables created.
  """
  connection = sqlite3.connect(db_filename, isolation_level=None)

  if discard_duplicates:
    key_column = '  request_log text primary key,\n'
  else:
    key_column = ''

  if custom_columns:
    custom_column_signature = (
        ', %s text\n' % ' text\n, '.join(custom_columns))
  else:
    custom_column_signature = ''

  table_signature = (
      'create table requests (\n'
      '%s'
      '  remotehost text,\n'
      '  user text,\n'
      '  request_time_str text,\n'
      '  request_time DATETIME,\n'  # Not yet really implemented.
      '  request_line text,\n'
      '  status int,\n'
      '  bytes int,\n'
      '  referer text,\n'
      '  useragent text,\n'
      '  host text,\n'
      '  ms int,\n'
      '  cpu_ms int,\n'
      '  api_cpu_ms int,\n'
      '  cpm_usd float,\n'
      '  queue_name text,\n'
      '  task_name text,\n'
      '  loading_request boolean,\n'
      '  pending_ms int,\n'
      '  exit_code int,\n'
      '  throttle_code int,\n'
      '  method text,\n'  # Not yet implemented.
      '  path text,\n'  # Not yet implemented.
      '  querystring text,\n'  # Not yet implemented.
      '  protocol text,\n'  # Not yet implemented.
      '  applog text,\n'
      '  applog0 text,\n'
      '  applog1 text,\n'
      '  applog2 text,\n'
      '  applog3 text,\n'
      '  applog4 text\n'
      '  %s'
      ')'
      ) % (key_column, custom_column_signature)
  try:
    connection.execute(table_signature)
  except sqlite3.OperationalError, e:
    if 'already exists' not in e.message:
      logging.exception('Exception creating table:')
      raise
    # TODO: Check that the schema matches.

  return connection


# An ugly regex to match the start of the request log line.
#            %h   %l    %u       %t          \"%r\"            %>s
#            %b       \"%{Referer}i\"    \"%{User-agent}i\""
LINE_RE = ('([^ ]+) - ([^ ]+) \[([^]]+)\] (-|"(\\\\.|[^"])*") ([^ ]+) '
           '([^ ]+) (-|"(\\\\.|[^"])*") (-|"(\\\\.|[^"])*")')
LINE_RE_COMPILED = re.compile(LINE_RE)


def parse_line(line, custom_columns):
  """Parse a line and return a dict of values.

  This is very cheesy code and totally hard coded.

  Args:
    line: A line from the log file.
    custom_columns: Dict of colname: regexp.

  Returns:
    Dictionary of values. If this is a request log line, it contains the
    various values from it. If it's an applog line, it contains two values
    'applog' with the value and 'applog_severity' with the severity, or ''
    meaning a continuation of the previous applog.

  Raises:
    LineParsingFailure: cannot parse the line.
  """
  results = {}
  if line.startswith('\t'):
    applog = line.strip()  # remove leading tab and trailing newline.
    results['applog'] = applog
    # Some applogs have severity; some are continuations and do not.
    if (len(applog) > 2 and applog[1] == ':'
        and applog[0] >= '0' and applog[0] <= '9'):
      results['applog_severity'] = applog[0]
    for column, regexp in custom_columns.iteritems():
      match = re.search(regexp, applog)
      if match:
        # TODO: Consider allowing named groups.
        results[column] = match.group(1)
    return results

  matches = LINE_RE_COMPILED.match(line)
  if not matches:
    raise LineParsingFailure('Fail. %s', line)

  results['remotehost'] = matches.group(1)
  results['user'] = matches.group(2)
  results['request_time_str'] = matches.group(3)
  results['request_line'] = matches.group(4)
  # Submatch = matches.group(5)
  results['status'] = matches.group(6)
  results['bytes'] = matches.group(7)
  results['referer'] = matches.group(8)
  # Submatch = matches.group(9)
  results['useragent'] = matches.group(10)

  more_values = line[len(matches.group(0)):].strip().split(' ')
  if more_values:
    results['host'] = more_values.pop(0)
  for pair in more_values:
    key, value = pair.split('=')
    results[key] = value
  if more_values and 'loading_request' not in results:
    # The user requested --include_all, so if this were a loading request
    # it would be in the line. But it's not in the line, so it's not a loading
    # request. Otherwise, we want it to be NULL for unknown.
    results['loading_request'] = '0'

  return results


def insert_row(row_dict, insert_cursor, discard_duplicates):
  """Insert a row into the database, including conversions if necessary.

  Args:
    row_dict: Dictionary of data to insert.
    insert_cursor: A cursor to the database to execute the insert on.
    discard_duplicates: If duplicates should be discarded.

  Returns:
    Boolean, True if the row was successfully inserted into the db, else False.
  """
  columns = []
  values = []
  # Calculating an insert statement may be vulnerable to sql injection. However,
  # this is an offline tool. Perhaps sqlite3 can handle this using sqlite3.Row?
  for column, value in row_dict.iteritems():
    columns.append(column)
    values.append(value)

  try:
    statement = ('insert into requests (%s) values (%s)' %
                 (','.join(columns), ','.join(['?'] * len(columns))))
    insert_cursor.execute(statement, values)
  except sqlite3.IntegrityError:
    if not discard_duplicates:
      # This should never happen anyway as we shouldn't have specified
      # a primary key. But if someone re-uses the db, it might.
      raise
    return False
  return True


def parse_log_file(lines, connection, discard_duplicates, custom_columns):
  """Parse every input line, insert it into the db as appropriate.

  Args:
    lines: Iterator returning log lines to parse.
    connection: Sqlite3 connection with the requests table created.
    discard_duplicates: If it should attempt to discard duplicate log lines.
    custom_columns: Dictionary, column name: regexp.

  Returns:
    request_count, insert_count: The number of requests seen, and the number
      inserted. (Will differ if discard_duplicates is true.)
  """
  result_dict = {}
  insert_cursor = connection.cursor()
  request_count = 0
  insert_count = 0
  applog_severity = ''
  for line in lines:
    parsed_line = parse_line(line, custom_columns)
    if 'applog' in parsed_line:
      # TODO: Discard the first severity 0 applog line, which seems to be
      # a variant of the requestlog line.
      applog = parsed_line.pop('applog')
      applog_severity = parsed_line.pop('applog_severity', applog_severity)
      result_dict['applog'] = result_dict.get('applog', '') + '\n' + applog
      if applog_severity:
        severity = 'applog%s' % applog_severity
        result_dict[severity] = result_dict.get(severity, '') + '\n' + applog
      # Everything else is a custom column. Last one wins.
      result_dict.update(parsed_line)
      continue
    # At this point we've reached a new line. Write the old one.
    if request_count % 100 == 0:
      print '.',
      sys.stdout.flush()
    request_count += 1
    if result_dict:
      inserted = insert_row(result_dict, insert_cursor, discard_duplicates)
      if inserted:
        insert_count += 1
    result_dict = parsed_line
    applog_severity = ''
    if discard_duplicates:
      result_dict['request_log'] = line

  # Add the last row.
  if result_dict:
    inserted = insert_row(result_dict, insert_cursor, discard_duplicates)
    if inserted:
      insert_count += 1

  connection.commit()
  insert_cursor.close()
  print ''
  return request_count, insert_count


def parse_arguments():
  """Parse arguments from sys.argv; exit if they are no good."""
  usage = 'usage: %prog [options] input_filename(s)'
  parser = optparse.OptionParser(usage=usage)
  parser.add_option('--db', dest='db', help='Filename of sqlite3 database.')
  parser.add_option('--discard_duplicates', dest='discard_duplicates',
                    action='store_true', default=False,
                    help='Discard duplicate request rows.')
  parser.add_option('--custom_column', dest='custom_columns', action='append',
                    help='Custom column (can be multiple); format is '
                    'name:regexp. Run across app logs.')

  options, args = parser.parse_args()

  errors = []
  if not args:
    errors.append('At least one input_filename is required.')
  required_flags = ('db',)
  for flag in required_flags:
    if not getattr(options, flag):
      errors.append('--%s is required' % flag)
  if errors:
    parser.print_help()
    print '\nErrors: '
    print '  ' + '\n  '.join(errors)
    sys.exit(1)

  input_filenames = args

  return options, input_filenames


def main():
  """Main function. Parse args then run over the log files."""
  options, input_filenames = parse_arguments()
  if options.custom_columns:
    custom_columns = dict(value.split(':', 1)
                          for value in options.custom_columns)
  else:
    custom_columns = {}

  connection = create_database(options.db, options.discard_duplicates,
                               custom_columns)

  request_count_total = 0
  insert_count_total = 0
  for filename in input_filenames:
    print 'Parsing %s' % filename
    f = open(filename, 'r')
    request_count, insert_count = parse_log_file(f, connection,
                                                 options.discard_duplicates,
                                                 custom_columns)
    request_count_total += request_count
    insert_count_total += insert_count

  print 'Done! Parsed %d requests. %d duplicate rows.' % (
      request_count_total, request_count_total - insert_count_total)


if __name__ == '__main__':
  main()
