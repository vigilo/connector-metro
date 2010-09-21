%define module  connector-metro
%define name    vigilo-%{module}
%define version 2.0.0
%define release 1%{?svn}%{?dist}

Name:       %{name}
Summary:    Vigilo Metrology connector
Version:    %{version}
Release:    %{release}
Source0:    %{name}-%{version}.tar.gz
URL:        http://www.projet-vigilo.org
Group:      System/Servers
BuildRoot:  %{_tmppath}/%{name}-%{version}-%{release}-build
License:    GPLv2

BuildRequires:   python-setuptools
BuildRequires:   python-babel

Requires:   python >= 2.5
Requires:   python-setuptools
Requires:   vigilo-common vigilo-connector
Requires:   rrdtool
######### Dependance from python dependance tree ########
Requires:   vigilo-pubsub
Requires:   vigilo-connector
Requires:   vigilo-common
Requires:   python-twisted
Requires:   python-wokkel
Requires:   python-configobj
Requires:   python-babel
Requires:   python-zope-interface
Requires:   python-setuptools
Requires:   python-twisted
Requires:   python-wokkel

Requires(pre): rpm-helper

Buildarch:  noarch


%description
Gateway from the Vigilo message bus (XMPP) to RRD files.
This application is part of the Vigilo Project <http://vigilo-project.org>

%prep
%setup -q

%build
make PYTHON=%{_bindir}/python

%install
rm -rf $RPM_BUILD_ROOT
make install_files \
	DESTDIR=$RPM_BUILD_ROOT \
	PREFIX=%{_prefix} \
	SYSCONFDIR=%{_sysconfdir} \
	LOCALSTATEDIR=%{_localstatedir} \
	PYTHON=%{_bindir}/python

%find_lang %{name}


%pre
%_pre_useradd vigilo-metro %{_localstatedir}/lib/vigilo/rrd /bin/false

%post
%_post_service %{name}

%preun
%_preun_service %{name}


%clean
rm -rf $RPM_BUILD_ROOT

%files -f %{name}.lang
%defattr(644,root,root,755)
%doc COPYING
%{_bindir}/%{name}
%attr(744,root,root) %{_initrddir}/%{name}
%dir %{_sysconfdir}/vigilo/
%dir %{_sysconfdir}/vigilo/%{module}
%config(noreplace) %{_sysconfdir}/vigilo/%{module}/settings.ini
%{_sysconfdir}/vigilo/%{module}/*.example
%config(noreplace) %{_sysconfdir}/sysconfig/*
%{python_sitelib}/*
%dir %{_localstatedir}/lib/vigilo
%attr(755,vigilo-metro,vigilo-metro) %{_localstatedir}/lib/vigilo/rrd
%attr(-,vigilo-metro,vigilo-metro) %{_localstatedir}/lib/vigilo/%{module}
%attr(-,vigilo-metro,vigilo-metro) %{_localstatedir}/run/%{name}


%changelog
* Mon Feb 08 2010 Aurelien Bompard <aurelien.bompard@c-s.fr> - 1.0-1
- initial package
