#! /bin/sh

sudo apt-get update
sudo apt-get install -y python-software-properties curl build-essential
sudo add-apt-repository ppa:hugin/hugin-builds
sudo apt-get update
sudo apt-get install -y hugin enblend libpano13-dev autopano-sift-c imagemagick unzip
sudo perl -MCPAN -e '$ENV{PERL_MM_USE_DEFAULT}=1; CPAN::Shell->install("Panotools::Script")'

# Needed for setup.py install as well as easy_install
sudo apt-get install python-setuptools

sudo easy_install boto


# Install the gtaskqueue tool from
# http://code.google.com/p/google-api-python-client/downloads/detail?name=google-api-python-client-1.0beta1.tar.gz&can=2&q=
# The gtaskqueue_sample is currently included in the sources but not in the
# tarball above yet. (Should change soon). Currently assume that we have the
# right tarball in the current directory.
tar xzvf google-api-python-client-1.0beta1.tar.gz
cd google-api-python-client-1.0beta1
# Installs the generic API client libraries.
sudo python setup.py install
# Installs the gtaskqueue tools
cd samples/gtaskqueue_sample
sudo python setup.py install
cd ~
