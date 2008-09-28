#!/bin/sh

PATH=/sbin:/bin:/usr/sbin:/usr/bin

user=network
group=network
pidfile=/var/run/wiremaps/wiremaps.pid
logfile=/var/log/wiremaps/wiremaps.log

test -x /usr/bin/twistd || exit 0

case "$1" in
    start)
        echo -n "Starting wiremaps: twistd"
        start-stop-daemon -c $user -g $group --start \
			  --quiet --exec /usr/bin/twistd -- \
                          --pidfile=$pidfile \
			  --no_save \
                          --logfile=$logfile \
	                  wiremaps --config=/etc/wiremaps/wiremaps.cfg
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
