DIR=$(dir $(abspath $(lastword $(MAKEFILE_LIST))))

SERVICE_NAME=http-tunnel
USER=$(SERVICE_NAME)

CODE_SRC=http-tunnel.py
CONF_SRC=http-tunnel.yml
SYSTEMD_SRC=systemd.service

CODE_DST=/usr/sbin/$(SERVICE_NAME)
CONF_DST=/etc/$(SERVICE_NAME).yml
SYSTEMD_DST=/etc/systemd/system/$(SERVICE_NAME).service

install: install-$(shell ps -o comm -p 1|tail -n 1)

erase: erase-$(shell ps -o comm -p 1|tail -n 1)

install-systemd:
	test $(shell id -u) == 0 || (echo "You must be root to install service"; exit 1)
	useradd --system --home-dir=/ --shell=$(shell which nologin) $(USER) || :
	cp ${DIR}$(CODE_SRC) $(CODE_DST)
	cp $(DIR)$(CONF_SRC) $(CONF_DST)
	chmod 755 $(CODE_DST)
	sed 's|{{USER}}|$(USER)|; s|{{EXEC}}|$(CODE_DST) $(CONF_DST)|' $(DIR)$(SYSTEMD_SRC) > $(SYSTEMD_DST)
	systemctl daemon-reload

erase-systemd:
	test $(shell id -u) == 0 || (echo "You must be root to erase service"; exit 1)
	systemctl stop $(SERVICE_NAME) || :
	rm -f $(SYSTEMD_DST)
	rm -f $(CODE_DST)
	rm -f $(CONF_DST)
	systemctl daemon-reload

install-init:
	echo "Not implemented yet for init"
	exit 1

erase-init:
	echo "Not implemented yet for init"
	exit 1
