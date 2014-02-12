#!/bin/sh
#
# Example init.d script for demo_scgi.py server

PATH=/bin:/usr/bin:/usr/local/bin
DAEMON=./demo_scgi.py
PIDFILE=/var/tmp/demo_scgi.pid

NAME=`basename $DAEMON`
case "$1" in
  start)
    if [ -f $PIDFILE ]; then
      if ps -p `cat $PIDFILE` > /dev/null 2>&1 ; then
        echo "$NAME appears to be already running ($PIDFILE exists)."
        exit 1
      else
        echo "$PIDFILE exists, but appears to be obsolete; removing it"
        rm $PIDFILE
      fi
    fi 

    echo -n "Starting $NAME: "
    env -i PATH=$PATH \
    	$DAEMON -P $PIDFILE -l /var/tmp/quixote-error.log
    echo "done"
    ;;

  stop)
    if [ -f $PIDFILE ]; then
      echo -n "Stopping $NAME: "
      kill `cat $PIDFILE`
      echo "done"
      if ps -p `cat $PIDFILE` > /dev/null 2>&1 ; then
      	echo "$NAME is still running, not removing $PIDFILE"
      else
        rm -f $PIDFILE
      fi
    else
      echo "$NAME does not appear to be running ($PIDFILE doesn't exist)."
    fi
    ;;

  restart)
    $0 stop
    $0 start
    ;;

  *)
    echo "Usage: $0 {start|stop|restart}"
    exit 1
    ;;
esac
