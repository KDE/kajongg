#!/bin/sh

# this is a simple test script setting up a situation where 4 human players
# may or may not start a game.

# it expects players wrmain, wr1, wr2, wr3 to already exist.

serverDebug=table,deferredBlock #,deferredBlock # ,deferredBlock # traffic,connections,process,deferredBlock
clientDebug=table # ,traffic # ,connections,traffic,process

killkajongg() {
	for signal in 15 9
	do
		ps axf | grep -e p[y]thon | grep -e k[a]$1 | grep -v $0 | grep -v -w vi | grep -v pylint | while read line
		do
			set - $line
			echo killing $line
			kill -$signal $1
		done
	done
}

killkajongg jongg.py
killkajongg jonggserver.py
sleep 2

./kajonggserver.py  --debug=$serverDebug &
sleep 1

./kajongg.py --host=localhost --player=wrmain --table --ruleset='Classical Chinese DMJL'  --debug=$clientDebug &
sleep 1

for other in wr1 wr2 wr3
do
	./kajongg.py --host=localhost --player=$other --join  --debug=$clientDebug &
done

sleep 50000
killclient
