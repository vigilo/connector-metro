NAME := connector-metro
USER := vigilo-metro
EPYDOC_PARSE := vigilo\.connector_metro\.nodetorrdtool

all: build settings.ini

include buildenv/Makefile.common
PKGNAME := vigilo-connector-metro

settings.ini: settings.ini.in
	sed -e 's,@LOCALSTATEDIR@,$(LOCALSTATEDIR),g;s,@SYSCONFDIR@,$(SYSCONFDIR),g' $^ > $@

install: install_python install_data install_permissions
install_pkg: install_python_pkg install_data

install_python: settings.ini $(PYTHON)
	$(PYTHON) setup.py install --root=$(DESTDIR) --record=INSTALLED_FILES
install_python_pkg: settings.ini $(PYTHON)
	$(PYTHON) setup.py install --single-version-externally-managed --root=$(DESTDIR)

install_data: pkg/init pkg/initconf pkg/init.rrdcached pkg/initconf.rrdcached
	# init
	install -p -m 755 -D pkg/init $(DESTDIR)/etc/rc.d/init.d/$(PKGNAME)
	echo /etc/rc.d/init.d/$(PKGNAME) >> INSTALLED_FILES
	install -p -m 644 -D pkg/initconf $(DESTDIR)$(INITCONFDIR)/$(PKGNAME)
	echo $(INITCONFDIR)/$(PKGNAME) >> INSTALLED_FILES
	# rrdcached
	install -p -m 755 -D pkg/init.rrdcached $(DESTDIR)/etc/rc.d/init.d/vigilo-rrdcached
	echo /etc/rc.d/init.d/vigilo-rrdcached >> INSTALLED_FILES
	install -p -m 644 -D pkg/initconf.rrdcached $(DESTDIR)$(INITCONFDIR)/vigilo-rrdcached
	echo $(INITCONFDIR)/vigilo-rrdcached >> INSTALLED_FILES

install_permissions:
	chown $(USER):$(USER) \
			$(DESTDIR)$(LOCALSTATEDIR)/lib/vigilo/rrd \
			$(DESTDIR)$(LOCALSTATEDIR)/lib/vigilo/$(NAME) \
            $(DESTDIR)$(LOCALSTATEDIR)/run/$(PKGNAME) \
			$(DESTDIR)$(LOCALSTATEDIR)/run/vigilo-rrdcached
	chmod 755 $(DESTDIR)$(LOCALSTATEDIR)/lib/vigilo/rrd

clean: clean_python
	rm -f settings.ini

lint: lint_pylint
tests: tests_nose

.PHONY: install_pkg install_python install_python_pkg install_data install_permissions
