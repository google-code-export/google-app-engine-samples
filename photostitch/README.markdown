## Overview

This sample is a AppEngine app and a worker setup that runs a photo stitching
service.

The basic architecture currently is this:

1. The user uploads a zip file with images via a web form.
2. The AppEngine app unzips this, chunks it up and uploads it to Google
Storage.
3. The AppEngine app then adds an item to a pull queue.
4. The worker polls the queue and grabs a work item.
5. The worker downloads the images, joins them, creates thumbnails and reuploads
them to Google Storage.
6. The worker stitches the images together using open source pano software.
7. After each step, the worker writes a state file to communicate what is going
on.
8. The AppEngine app reads these state files from Google Storage and uses the
info to render a page with links to past stitches.

## Install

Right now installing this is a bit of a mess.

To set up the AppEngine app (photostitch dir):

1. Create a new AppEngine application.
2. Modify Makefile to point to where your AppEngine SDK is.
3. Download boto and apiclient, untar them into the photostitch/ directory.
   boto can be got from : https://github.com/boto/boto
   apiclient can be downloaded from :
http://code.google.com/p/google-api-python-client/source/browse/#hg%2Fapiclient
4. Deploy/push your application with 'make update'

For details on setting up and running the worker code, see worker/README.
