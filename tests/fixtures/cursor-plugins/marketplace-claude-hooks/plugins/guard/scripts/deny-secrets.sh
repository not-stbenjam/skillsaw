#!/bin/sh
# Refuse shell commands that read the production secrets store.
grep -q 'prod/secrets' && exit 2
exit 0
