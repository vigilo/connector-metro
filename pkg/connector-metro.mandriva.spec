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
Buildarch:  noarch

BuildRequires:   python-setuptools
BuildRequires:   python-babel

Requires:   python >= 2.5
Requires:   python-setuptools
Requires:   vigilo-common vigilo-connector
Requires:   rrdtool
Requires:   sqlite3-tools
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


# VigiConf
Requires:   vigilo-vigiconf-local
Obsoletes:  %{name}-vigiconf < 2.0.0-1.svn5779
Provides:   %{name}-vigiconf = %{version}-%{release}

%description
Gateway from the Vigilo message bus (XMPP) to RRD files.
This application is part of the Vigilo Project <http://vigilo-project.org>

%package    -n vigilo-rrdcached
Summary:    RRD cache daemon
Group:      System/Servers
Requires:   rrdtool >= 1.4
# a cause des droits sur les fichiers (vigilo-metro)
Requires(pre):   %{name}

%description -n vigilo-rrdcached
This contains an init script and configuration files to use the RRD cache
daemon within Vigilo.
This package is part of the Vigilo Project <http://vigilo-project.org>


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

%post -n vigilo-rrdcached
%_post_service vigilo-rrdcached

%preun -n vigilo-rrdcached
%_preun_service vigilo-rrdcached


%clean
rm -rf $RPM_BUILD_ROOT

%files -f %{name}.lang
%defattr(644,root,root,755)
%doc COPYING
%attr(755,root,root) %{_bindir}/*
%attr(744,root,root) %{_initrddir}/%{name}
%dir %{_sysconfdir}/vigilo/
%dir %{_sysconfdir}/vigilo/%{module}
%attr(640,root,vigilo-metro) %config(noreplace) %{_sysconfdir}/vigilo/%{module}/settings.ini
%config(noreplace) %{_sysconfdir}/sysconfig/%{name}
%{python_sitelib}/*
%dir %{_localstatedir}/lib/vigilo
%attr(755,vigilo-metro,vigilo-metro) %{_localstatedir}/lib/vigilo/rrd
%attr(-,vigilo-metro,vigilo-metro) %{_localstatedir}/lib/vigilo/%{module}
%attr(-,vigilo-metro,vigilo-metro) %{_localstatedir}/run/%{name}

%files -n vigilo-rrdcached
%defattr(644,root,root,755)
%attr(744,root,root) %{_initrddir}/vigilo-rrdcached
%config(noreplace) %{_sysconfdir}/sysconfig/vigilo-rrdcached
%attr(-,vigilo-metro,vigilo-metro) %{_localstatedir}/run/vigilo-rrdcached


%changelog
* Mon Feb 08 2010 Aurelien Bompard <aurelien.bompard@c-s.fr> - 1.0-1
- initial package
