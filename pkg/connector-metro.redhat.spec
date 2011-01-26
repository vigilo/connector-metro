%define module  connector-metro
%define name    vigilo-%{module}
%define version 2.0.0
%define release 1%{?svn}%{?dist}

%define pyver 26
%define pybasever 2.6
%define __python /usr/bin/python%{pybasever}
%define __os_install_post %{__python26_os_install_post}
%{!?python26_sitelib: %define python26_sitelib %(python26 -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}

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

BuildRequires:   python26-distribute
BuildRequires:   python26-babel

Requires:   python26-distribute
Requires:   vigilo-common vigilo-connector
Requires:   rrdtool
Requires:   sqlite >= 3

Requires(pre): shadow-utils
Requires(post): chkconfig
Requires(preun): chkconfig
# This is for /sbin/service
Requires(preun): initscripts
Requires(postun): initscripts

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
Requires:   %{name}
Requires:   rrdtool >= 1.4

%description -n vigilo-rrdcached
This contains an init script and configuration files to use the RRD cache
daemon within Vigilo.
This package is part of the Vigilo Project <http://vigilo-project.org>


%prep
%setup -q

%build
make PYTHON=%{__python}

%install
rm -rf $RPM_BUILD_ROOT
make install_files \
    DESTDIR=$RPM_BUILD_ROOT \
    PREFIX=%{_prefix} \
    SYSCONFDIR=%{_sysconfdir} \
    LOCALSTATEDIR=%{_localstatedir} \
    PYTHON=%{__python}

%find_lang %{name}


%pre
getent group vigilo-metro >/dev/null || groupadd -r vigilo-metro
getent passwd vigilo-metro >/dev/null || useradd -r -g vigilo-metro -d %{_localstatedir}/lib/vigilo/rrd -s /sbin/nologin vigilo-metro
exit 0

%post
/sbin/chkconfig --add %{name} || :

%preun
if [ $1 = 0 ]; then
    /sbin/service %{name} stop > /dev/null 2>&1 || :
    /sbin/chkconfig --del %{name} || :
fi

%postun
if [ "$1" -ge "1" ] ; then
    /sbin/service %{name} condrestart > /dev/null 2>&1 || :
fi

%post -n vigilo-rrdcached
/sbin/chkconfig --add vigilo-rrdcached || :

%preun -n vigilo-rrdcached
if [ $1 = 0 ]; then
    /sbin/service vigilo-rrdcached stop > /dev/null 2>&1 || :
    /sbin/chkconfig --del vigilo-rrdcached || :
fi

%postun -n vigilo-rrdcached
if [ "$1" -ge "1" ] ; then
    /sbin/service vigilo-rrdcached condrestart > /dev/null 2>&1 || :
fi


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
%{python26_sitelib}/*
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
