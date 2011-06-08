#! /bin/sh
gtaskqueue_puller --taskqueue_name=photostitch \
  --project_name=appid:your-gae-app-id \
  --min_running_tasks=4 \
  --num_tasks=8 \
  --sleep_interval_secs=5 \
  --lease_secs=600 \
  --executable_binary=./do_stitch.py

