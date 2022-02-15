Ansible Role: paperless-ng
==========================

Installs and configures paperless-ng EDMS on Debian/Ubuntu systems.

Requirements
------------

No special system requirements. Ansible 2.7 or newer is required.

Note that this role requires root access, so either run it in a playbook with a global `become: yes`, or invoke the role in your playbook like:

    - hosts: all
      roles:
        - role: paperless-ng
          become: yes

Role Variables
--------------

Most configuration variables from paperless-ng itself are available and accept their respective arguments.
Every `PAPERLESS_*` configuration variable is lowercased and instead prefixed with `paperlessng_*` in `defaults/main.yml`.

For a full listing including explanations and allowed values, see the current [documentation](https://paperless-ng.readthedocs.io/en/latest/configuration.html).

Additional variables available in this role are listed below, along with default values:

    paperlessng_version: latest

The [release](https://github.com/jonaswinkler/paperless-ng/releases) archive version of paperless-ng to install.
`latest` stands for the latest release of paperless-ng.
To install a specific version of paperless-ng, use the tag name of the release, e. g. `ng-1.4.4`, or specify a branch or commit id.

    paperlessng_redis_host: localhost
    paperlessng_redis_port: 6379

Separate configuration values that combine into `PAPERLESS_REDIS`.

    paperlessng_db_type: sqlite

Database to use. Default is file-based SQLite.

    paperlessng_db_host: localhost
    paperlessng_db_port: 5432
    paperlessng_db_name: paperlessng
    paperlessng_db_user: paperlessng
    paperlessng_db_pass: paperlessng
    paperlessng_db_sslmode: prefer

Database configuration (only applicable if `paperlessng_db_type == 'postgresql'`).

    paperlessng_directory: /opt/paperless-ng

Root directory paperless-ng is installed into.

    paperlessng_virtualenv: "{{ paperlessng_directory }}/.venv"

Directory used for the virtual environment for paperless-ng.

    paperlessng_ocr_languages:
      - eng

List of OCR languages to install and configure (`apt search tesseract-ocr-*`).

    paperlessng_use_jbig2enc: True

Whether to install and use [jbig2enc](https://github.com/agl/jbig2enc) for OCRmyPDF.

    paperlessng_big2enc_lossy: False

Whether to use jbig2enc's lossy compression mode.

    paperlessng_superuser_name: paperlessng
    paperlessng_superuser_email: paperlessng@example.com
    paperlessng_superuser_password: paperlessng

Credentials of the initial superuser in paperless-ng.

    paperlessng_system_user: paperlessng
    paperlessng_system_group: paperlessng

System user and group to run the paperless-ng services as (will be created if required).

    paperlessng_listen_address: 127.0.0.1
    paperlessng_listen_port: 8000

Address and port for the paperless-ng service to listen on.

Dependencies
------------

No ansible dependencies.

Example Playbook
----------------
`playbook.yml`:

    - hosts: all
      become: yes
      vars_files:
        - vars/paperless-ng.yml
      roles:
        - paperless-ng

`vars/paperless-ng.yml`:

    paperlessng_media_root: /mnt/media/smbshare

    paperlessng_db_type: postgresql
    paperlessng_db_pass: PLEASEPROVIDEASTRONGPASSWORDHERE

    paperlessng_secret_key: AGAINPLEASECHANGETHISNOW

    paperlessng_ocr_languages:
      - eng
      - deu
