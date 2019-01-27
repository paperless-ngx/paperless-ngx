#!/usr/bin/env bash

# Bash script to install paperless in lxc containter
# paperless.lan
#
# Will set-up paperless, apache2 and proftpd
#
# lxc launch ubuntu: paperless
# lxc exec paperless -- sh -c "wget https://raw.githubusercontent.com/danielquinn/paperless/master/scripts/lxc/lxc-install.sh && /bin/bash lxc-install.sh"
#
#

# Add paperless user with no password
adduser --disabled-password --gecos "" paperless
# Add ftpupload
adduser --disabled-password --gecos "" ftpupload
echo "Set ftpupload password: "
passwd ftpupload
# Allow paperless group to access
adduser paperless ftpupload
chmod g+w /home/ftpupload 

# Get apt up to date
apt-get update

# Needed for plain Paperless
apt-get -y install unpaper gnupg libpoppler-cpp-dev python3-pyocr tesseract-ocr imagemagick optipng

# Needed for Apache
apt-get -y install apache2 libapache2-mod-wsgi-py3

# Install ftp server and make sure all uplaoded files are owned by paperless
apt-get -y install proftpd
cat <<EOF >> /etc/proftpd/proftpd.conf
<Directory /home/ftpupload/>
  UserOwner   paperless
  GroupOwner  paperless
</Directory>
EOF
systemctl restart proftpd


#Get Paperless from git 
su -c "cd /home/paperless ; git clone https://github.com/danielquinn/paperless" paperless

# Install Pip Requirements
apt-get -y install python3-pip python3-venv
cd /home/paperless/paperless
pip3 install -r requirements.txt

# Take paperless.conf.example and set consumuption dir (ftp dir)
sed  -e '/PAPERLESS_CONSUMPTION_DIR=/s/=.*/=\"\/home\/ftpupload\/\"/' \
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
cp /home/paperless/paperless/docs/examples/lxc/paperless.conf /etc/apache2/sites-available/
a2dissite 000-default.conf
a2ensite paperless.conf
systemctl reload apache2

sed -e "s/home\/paperless\/project\/virtualenv\/bin\/python/usr\/bin\/python3/" \
     /home/paperless/paperless/scripts/paperless-consumer.service \
     >/etc/systemd/system/paperless-consumer.service

sed  -i "s/\/home\/paperless\/project\/src\/manage.py/\/home\/paperless\/paperless\/src\/manage.py/" \
      /etc/systemd/system/paperless-consumer.service


systemctl enable paperless-consumer
systemctl start paperless-consumer

# convert-im6.q16: not authorized
# Security risk ?
# https://stackoverflow.com/questions/42928765/convertnot-authorized-aaaa-error-constitute-c-readimage-453
mv /etc/ImageMagick-6/policy.xml /etc/ImageMagick-6/policy.xmlout
