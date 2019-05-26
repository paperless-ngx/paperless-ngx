#!/usr/bin/env bash

# Bash script to install paperless in lxc containter
# paperless.lan
#
# Will set-up paperless, apache2 and proftpd
#
# lxc launch ubuntu: paperless
# lxc exec paperless -- sh -c "sudo apt-get update && sudo apt-get install -y wget"
# lxc exec paperless -- sh -c "wget https://raw.githubusercontent.com/the-paperless-project/paperless/master/docs/examples/lxc/lxc-install.sh && /bin/bash lxc-install.sh --email "
#
#
set +e
PASSWORD=$(< /dev/urandom tr -dc _A-Z-a-z-0-9+@%^{} | head -c20;echo;)
EMAIL=

function displayHelp() {
    echo "available parameters:
    -e <email> | --email <email> 
    -p <password> | --password <password>
    "
}

POSITIONAL=()
while [[ $# -gt 0 ]]
do
key="$1"
i=$key

case $i in
    -e|--email)
      EMAIL="${2}"
      shift
      shift
    ;;
    -p|--password)
      PASSWORD="${2}"
      shift
      shift
    ;;
    --default|-h|--help)
      shift
      displayHelp
      exit 0
    ;;
    *)
      echo "argument: $i not recognized"
      exit 2
    ;;
esac
done
set -- "${POSITIONAL[@]}" # restore positional parameters

if [ -z $EMAIL ]; then
  echo "missing email, try running with -h "
  exit 3
fi
if [[ $(/usr/bin/id -u) -ne 0 ]]; then
    echo "Not running as root"
    exit
fi

if [ $(grep -c paperless /etc/passwd) -eq 0 ]; then
  # Add paperless user with no password
  adduser --disabled-password --gecos "" paperless
fi

if [ $(grep -c ftpupload /etc/passwd) -eq 0 ]; then
  # Add ftpupload
  adduser --disabled-password --gecos "" ftpupload
  echo "Set ftpupload password: "
  #passwd ftpupload
  #TODO: generate some password and allow parameter 
  echo "ftpupload:ftpuploadpassword" | chpasswd
fi

if [ $(id -nG paperless | grep -Fcw ftpupload) -eq 0 ]; then
  # Allow paperless group to access
  adduser paperless ftpupload
  chmod g+w /home/ftpupload 
fi

# Get apt up to date
apt-get update

# Needed for plain Paperless
apt-get -y install unpaper gnupg libpoppler-cpp-dev python3-pyocr tesseract-ocr imagemagick optipng git

# Needed for Apache
apt-get -y install apache2 libapache2-mod-wsgi-py3

if [ ! -f /etc/proftpd/proftpd.conf -o $(grep -c paperless /etc/proftpd/proftpd.conf) -eq 0 ]; then
  # Install ftp server and make sure all uplaoded files are owned by paperless
  apt-get -y install proftpd
  cat <<EOF >> /etc/proftpd/proftpd.conf
  <Directory /home/ftpupload/>
    UserOwner   paperless
    GroupOwner  paperless
  </Directory>
EOF
  systemctl restart proftpd
fi

#Get Paperless from git 
su -c "cd /home/paperless ; git clone https://github.com/the-paperless-project/paperless" paperless

# Install Pip Requirements
apt-get -y install python3-pip python3-venv
cd /home/paperless/paperless
pip3 install -r requirements.txt

# Take paperless.conf.example and set consumuption dir (ftp dir)
sed  -e '/PAPERLESS_CONSUMPTION_DIR=/s/=.*/=\"\/home\/ftpupload\/\"/' \
     /home/paperless/paperless/paperless.conf.example  >/etc/paperless.conf

# Update /etc/paperless.conf with PAPERLESS_SECRET_KEY
SECRET=$(strings /dev/urandom | grep -o '[[:alnum:]]' | head -n 30 | tr -d '\n'; echo)
sed  -i "s/#PAPERLESS_SECRET_KEY.*/PAPERLESS_SECRET_KEY=$SECRET/" /etc/paperless.conf 

#Initialise the SQLite database 
su -c "cd /home/paperless/paperless/src/ ; ./manage.py migrate" paperless
echo "if superuser doesn't exists, create one with login: paperless and password: ${PASSWORD}"
#Create a user for your Paperless instance
su -c "cd /home/paperless/paperless/src/ ; echo ./manage.py create_superuser_with_password --username paperless --email ${EMAIL} --password ${PASSWORD} --preserve" paperless
su -c "cd /home/paperless/paperless/src/ ; ./manage.py create_superuser_with_password --username paperless --email ${EMAIL} --password ${PASSWORD} --preserve" paperless

if [ ! -d /home/paperless/paperless/static ]; then
  # 167 static files copied to '/home/paperless/paperless/static'.
  su -c "cd /home/paperless/paperless/src/ ; ./manage.py collectstatic" paperless
fi

if [ ! -f /etc/apache2/sites-available/paperless.conf ]; then
  # Set-up apache
  cp /home/paperless/paperless/docs/examples/lxc/paperless.conf /etc/apache2/sites-available/
  a2dissite 000-default.conf
  a2ensite paperless.conf
  systemctl reload apache2
fi

sed -e "s:home/paperless/project/virtualenv/bin/python:usr/bin/python3:" \
     /home/paperless/paperless/scripts/paperless-consumer.service \
     >/etc/systemd/system/paperless-consumer.service

sed -i "s:/home/paperless/project/src/manage.py:/home/paperless/paperless/src/manage.py:" \
      /etc/systemd/system/paperless-consumer.service


systemctl enable paperless-consumer
systemctl start paperless-consumer

# convert-im6.q16: not authorized
# Security risk ?
# https://stackoverflow.com/questions/42928765/convertnot-authorized-aaaa-error-constitute-c-readimage-453
if [ -f /etc/ImageMagick-6/policy.xml ]; then
  mv /etc/ImageMagick-6/policy.xml /etc/ImageMagick-6/policy.xmlout
fi
