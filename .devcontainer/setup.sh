# Uncomment this when it is used with plain docker
# echo "START REDIS SERVER --------------------------------"
# redis-server &

echo "INSTALL DEVELOPER TOOLS ---------------------------"
pre-commit install

echo "INSTALL BACKEND DEPENDENCIES ----------------------"
pip3 install -r requirements.txt 
pipenv install --dev --system

echo "INSTALL FRONTEND DEPENDENCIES ---------------------"
cd src-ui
npm install
echo "BUILD FRONTEND ------------------------------------"
export NG_CLI_ANALYTICS=ci && node_modules/.bin/ng build --configuration production

echo "COPY AND CREATE REQUIRED FILES AND FOLDERS --------"
cd ..
cp paperless.conf.example paperless.conf
sed -i 's/#PAPERLESS_DEBUG=false/PAPERLESS_DEBUG=true/g' paperless.conf
mkdir -p consume media

echo "SETUP DATABASE ------------------------------------"
cd src
python3 manage.py migrate
export DJANGO_SUPERUSER_PASSWORD=admin && python3 manage.py createsuperuser --noinput --username admin --email admin@example.com
