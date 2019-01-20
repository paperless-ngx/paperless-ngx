#!/usr/bin/env bash

# Bash script to instal paperless in lxc containter

# Get apt up to date
apt-get update

# Needed for plain Paperless
apt-get -y install unpaper gnupg libpoppler-cpp-dev python3-pyocr tesseract-ocr imagemagick optipng

# Needed for Apache
apt-get -y install apache2 libapache2-mod-wsgi-py3
# paperless user
adduser --disabled-password --gecos "" paperless

#Get Paperless from git (NB: currently fork)
su -c "cd /home/paperless ; git clone https://github.com/bmsleight/paperless" paperless

# Install Pip Requirements
apt-get -y install python3-pip python3-venv
cd /home/paperless/paperless
pip3 install -r requirements.txt

#Set up consume directory
su -c "mkdir /home/paperless/consume" paperless

# Take paperless.conf.example and set consumuption dir
sed  -e '/PAPERLESS_CONSUMPTION_DIR=/s/=.*/=\"\/home\/paperless\/consume\/\"/' \
     /home/paperless/paperless/paperless.conf.example  >/etc/paperless.conf

# Update /etc/paperless.conf with PAPERLESS_SECRET_KEY
SECRET=$(strings /dev/urandom | grep -o '[[:alnum:]]' | head -n 30 | tr -d '\n'; echo)
sed  -i "s/#PAPERLESS_SECRET_KEY.*/PAPERLESS_SECRET_KEY=$SECRET/g" /etc/paperless.conf 

#Initialise the SQLite database 
su -c "cd /home/paperless/paperless/src/ ; ./manage.py migrate" paperless
#Create a user for your Paperless instance
su -c "cd /home/paperless/paperless/src/ ; ./manage.py createsuperuser" paperless
# 167 static files copied to '/home/paperless/paperless/static'.
su -c "cd /home/paperless/paperless/src/ ; ./manage.py collectstatic" paperless

# Set-up apache
cp /home/paperless/paperless/scripts/lxc/paperless.conf /etc/apache2/sites-available/
a2dissite 000-default.conf
a2ensite paperless.conf
systemctl reload apache2
