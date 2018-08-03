%define module  @SHORT_NAME@

Name:       vigilo-%{module}
Summary:    @SUMMARY@
Version:    @VERSION@
Release:    @RELEASE@%{?dist}
Source0:    %{name}-%{version}.tar.gz
URL:        @URL@
Group:      Applications/System
BuildRoot:  %{_tmppath}/%{name}-%{version}-%{release}-build
License:    GPLv2
Buildarch:  noarch

BuildRequires:   systemd
BuildRequires:   python-distribute
BuildRequires:   python-babel

Requires:   python-distribute
Requires:   python-lxml >= 3.0.1
Requires:   vigilo-common vigilo-connector
Requires:   rrdtool
Requires:   sqlite >= 3

# Init
Requires(pre): shadow-utils

# VigiConf
Requires:   vigilo-vigiconf-local
Obsoletes:  %{name}-vigiconf < 2.0.0-1.svn5779
Provides:   %{name}-vigiconf = %{version}-%{release}

%description
@DESCRIPTION@
This application is part of the Vigilo Project <https://www.vigilo-nms.com>

%package    -n vigilo-rrdcached
Summary:    RRD cache daemon
Group:      Applications/System

BuildRequires:   systemd

Requires:   rrdtool >= 1.4
# a cause des droits sur les fichiers (vigilo-metro)
Requires(pre):   %{name}
Requires(pre):   shadow-utils

%description -n vigilo-rrdcached
This contains an init script and configuration files to use the RRD cache
daemon within Vigilo.
This package is part of the Vigilo Project <https://www.vigilo-nms.com>


%prep
%setup -q

%build

%install
rm -rf $RPM_BUILD_ROOT
make install_pkg_systemd \
    DESTDIR=$RPM_BUILD_ROOT \
    PREFIX=%{_prefix} \
    SYSCONFDIR=%{_sysconfdir} \
    LOCALSTATEDIR=%{_localstatedir} \
    SYSTEMDDIR=%{_unitdir} \
    PYTHON=%{__python}
mkdir -p $RPM_BUILD_ROOT/%{_tmpfilesdir}
install -m 644 pkg/%{name}.conf $RPM_BUILD_ROOT/%{_tmpfilesdir}
install -m 644 pkg/vigilo-rrdcached.conf $RPM_BUILD_ROOT/%{_tmpfilesdir}

%find_lang %{name}


%pre
getent group vigilo-metro >/dev/null || groupadd -r vigilo-metro
getent passwd vigilo-metro >/dev/null || useradd -r -g vigilo-metro -d %{_localstatedir}/lib/vigilo/rrd -s /sbin/nologin vigilo-metro
exit 0

%post
%systemd_post %{name}.service
%{_libexecdir}/twisted-dropin-cache >/dev/null 2>&1 || :
%tmpfiles_create %{_tmpfilesdir}/%{name}.conf

%preun
%systemd_preun %{name}.service

%postun
%systemd_postun_with_restart %{name}.service
%{_libexecdir}/twisted-dropin-cache >/dev/null 2>&1 || :

%post -n vigilo-rrdcached
%systemd_post vigilo-rrdcached.service
%tmpfiles_create %{_tmpfilesdir}/vigilo-rrdcached.conf

%preun -n vigilo-rrdcached
%systemd_preun vigilo-rrdcached.service

%postun -n vigilo-rrdcached
%systemd_postun_with_restart vigilo-rrdcached.service

%clean
rm -rf $RPM_BUILD_ROOT

%files -f %{name}.lang
%defattr(644,root,root,755)
%doc COPYING.txt README.txt
%attr(755,root,root) %{_bindir}/*
%dir %{_sysconfdir}/vigilo/
%dir %{_sysconfdir}/vigilo/%{module}
%attr(640,root,vigilo-metro) %config(noreplace) %{_sysconfdir}/vigilo/%{module}/settings.ini
%{python_sitelib}/vigilo*
%{python_sitelib}/twisted*
%dir %{_localstatedir}/lib/vigilo
%attr(755,vigilo-metro,vigilo-metro) %{_localstatedir}/lib/vigilo/rrd
%attr(-,vigilo-metro,vigilo-metro) %{_localstatedir}/lib/vigilo/%{module}
%dir %{_localstatedir}/log/vigilo
%attr(-,vigilo-metro,vigilo-metro) %{_localstatedir}/log/vigilo/%{module}
%attr(644,root,root) %{_tmpfilesdir}/%{name}.conf
%attr(644,root,root) %{_unitdir}/%{name}.service
%attr(644,root,root) %{_unitdir}/%{name}@.service

%files -n vigilo-rrdcached
%defattr(644,root,root,755)
%doc COPYING.txt README.txt
%attr(644,root,root) %{_tmpfilesdir}/vigilo-rrdcached.conf
%attr(644,root,root) %{_unitdir}/vigilo-rrdcached.service

%changelog
* Tue Jun 27 2017 François Poirotte <francois.poirotte@c-s.fr>
- Add support for systemd

* Thu Mar 16 2017 Yves Ouattara <yves.ouattara@c-s.fr>
- Rebuild for RHEL7.

* Fri Jan 21 2011 Vincent Quéméner <vincent.quemener@c-s.fr>
- Rebuild for RHEL6.

* Mon Feb 08 2010 Aurelien Bompard <aurelien.bompard@c-s.fr>
- initial package
