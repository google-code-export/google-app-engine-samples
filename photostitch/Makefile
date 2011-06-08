# You will probably want to edit these variables

# App engine
SDK_BASE=path/to/appengine/sdk
APPID=your-gae-app-id
PASS=your-gae-app-specific-password
# The app engine account's email
APP_EMAIL=your-email@domain.com

# Google storage
GS_ACCESS_KEY=GOOGLE_STORAGE_ACCESS_KEY
GS_SECRET_KEY=GOOGLE_STORAGE_SECRET_KEY
GS_BUCKET=your-google-storage-bucket

# Task Queue
# The email that needs access to the pull queue
QUEUE_EMAIL=$(APP_EMAIL)

# You probably won't need to edit these variables
# Use this version if your app is highly-available
# REST_PROJECT=s~$(APPID)
REST_PROJECT=$(APPID)

APPCFG=$(SDK_BASE)/appcfg.py
DEV_SERVER=$(SDK_BASE)/dev_appserver.py

APPCFG_FLAGS=
APPCFG_FLAGS:=$(APPCFG_FLAGS) -e $(APP_EMAIL)

GS_CONFIG=\# DO NOT EDIT THIS GENERATED FILE DIRECTLY; EDIT THE Makefile\n\
			gs_access_key = '$(GS_ACCESS_KEY)'\n\
			gs_secret_key = '$(GS_SECRET_KEY)'\n\
			gs_bucket = '$(GS_BUCKET)'\n

config:
	@sed -i 's/^application: *.*/application: $(APPID)/' photostitch/app.yaml
	@sed -i 's/-project_name=[^ ]*/-project_name=$(REST_PROJECT)/' \
			worker/service_queue.sh
	@sed -i 's/^  - user_email: *.*/  - user_email: $(QUEUE_EMAIL)/' \
			photostitch/queue.yaml
	@echo -e "$(GS_CONFIG)" | sed 's/^ *//' > photostitch/config.py
	@echo -e "$(GS_CONFIG)" | sed 's/^ *//' > worker/config.py

setup: config


run:
	$(DEV_SERVER) --address=$(shell hostname) --port=8000 photostitch

update: config
	@echo $(PASS) | $(APPCFG) $(APPCFG_FLAGS) --passin update photostitch

uq: config
	@echo $(PASS) | $(APPCFG) $(APPCFG_FLAGS) --passin update_queues photostitch

lq:
	gtaskqueue listtasks --project_name='$(REST_PROJECT)' --taskqueue_name photostitch

clean:
	find . -name '*.pyc' -delete

send:
	curl --data-binary @fwd.zip http://$(shell hostname):8000/upload/testbatch
