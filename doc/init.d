#!/bin/sh

PATH=/sbin:/bin:/usr/sbin:/usr/bin

# Change this path before using this script!
# $basedir/wiremaps.tac should exist.
basedir=/path/to/directory/containing/wiremaps

rundir=$basedir
pidfile=$basedir/../wiremaps.pid
file=wiremaps.tac
logfile=$basedir/../wiremaps.log

test -x /usr/bin/twistd || exit 0
test -d $basedir || exit 0

case "$1" in
    start)
        echo -n "Starting wiremaps: twistd"
        start-stop-daemon -d $rundir -c network -g network --start \
			  --quiet --exec /usr/bin/twistd -- \
                          --pidfile=$pidfile \
			  --no_save \
                          --python=$file \
                          --logfile=$logfile
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
