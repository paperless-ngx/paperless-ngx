# -*- mode: ruby -*-
# vi: set ft=ruby :

VAGRANT_API_VERSION = "2"
Vagrant.configure(VAGRANT_API_VERSION) do |config|
  config.vm.box = "ubuntu/trusty64"

  # Provision using shell
  #config.vm.provision "shell", path: "vagrant/setup.sh"
  config.vm.host_name = "dev.paperless"
  config.vm.synced_folder ".", "/opt/paperless"
  config.vm.provision "shell", path: "vagrant/setup.sh"  
    
  # Networking details
  config.vm.network "private_network", ip: "172.28.128.4"
end
