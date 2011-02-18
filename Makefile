NAME := connector-metro
USER := vigilo-metro
EPYDOC_PARSE := vigilo\.connector_metro\.nodetorrdtool

all: build settings.ini

include buildenv/Makefile.common
PKGNAME := vigilo-connector-metro

settings.ini: settings.ini.in
	sed -e 's,@LOCALSTATEDIR@,$(LOCALSTATEDIR),g;s,@SYSCONFDIR@,$(SYSCONFDIR),g' $^ > $@

install: install_files install_permissions

install_files: settings.ini $(PYTHON)
	$(PYTHON) setup.py install --single-version-externally-managed --root=$(DESTDIR) --record=INSTALLED_FILES
	chmod a+rX -R $(DESTDIR)$(PREFIX)/lib*/python*/*
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
			$(LOCALSTATEDIR)/lib/vigilo/rrd \
			$(LOCALSTATEDIR)/lib/vigilo/$(NAME) \
            $(LOCALSTATEDIR)/run/$(PKGNAME) \
			$(LOCALSTATEDIR)/run/vigilo-rrdcached
	chmod 755 $(LOCALSTATEDIR)/lib/vigilo/rrd

clean: clean_python
	rm -f settings.ini

lint: lint_pylint
tests: tests_nose
