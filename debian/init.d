#!/bin/sh
### BEGIN INIT INFO
# Provides:          wiremaps
# Required-Start:    $remote_fs $syslog
# Required-Stop:     $remote_fs $syslog
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: Wiremaps
# Description:       layer 2 network discovery application
### END INIT INFO

PATH=/sbin:/bin:/usr/sbin:/usr/bin

user=wiremaps
group=wiremaps
pidfile=/var/run/wiremaps/wiremaps.pid
logfile=/var/log/wiremaps/wiremaps.log
configfile=/etc/wiremaps/wiremaps.cfg

test -x /usr/bin/twistd || exit 0
test -f $configfile || exit 0

version="$(twistd --version | head -1 | awk '{print $NF}')"

case "$1" in
    start)
        echo -n "Starting wiremaps: twistd"
	case "$version" in
	    8.*)
		start-stop-daemon -c $user -g $group --start \
		    --quiet --exec /usr/bin/twistd -- \
                    --pidfile=$pidfile \
		    --no_save \
                    --logfile=$logfile \
	            wiremaps --config=/etc/wiremaps/wiremaps.cfg
		;;
	    *)
		start-stop-daemon -c $user -g $group --start \
		    --quiet --exec /usr/bin/twistd -- \
                    --pidfile=$pidfile \
		    --no_save \
                    --logfile=$logfile \
	            --python $(python -c 'import imp ; print imp.find_module("wiremaps/core/tac")[1]')
		;;
	esac
        echo "."	
    ;;

    stop)
        echo -n "Stopping wiremaps: twistd"
        start-stop-daemon --stop --quiet  \
            --pidfile $pidfile
        echo "."	
    ;;

    restart)
        $0 stop
        $0 start
    ;;

    force-reload)
        $0 restart
    ;;

    *)
        echo "Usage: /etc/init.d/wiremaps {start|stop|restart|force-reload}" >&2
        exit 1
    ;;
esac

exit 0
