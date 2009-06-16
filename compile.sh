#!/bin/sh

# this file is only meant for the developer, please adapt
# to your environment

translate() {
	cd /home/wr/files/src/games-de
	svn up
	svn cat svn+ssh://wrohdewald@svn.kde.org/home/kde/trunk/l10n-kde4/templates/messages/playground-games/kmj.pot>kmj.pot
	msgmerge -o kmj.new kmj.po kmj.pot
	mv kmj.new kmj.po
	lokalize kmj.po

# compile and install the message files
	msgfmt -o kmj.mo kmj.po
	sudo cp kmj.mo /usr/share/locale/de/LC_MESSAGES
}

srcdir=`pwd -P`
for i in *.ui
do
	pyuic4 $i > ${i%.ui}_ui.py
done
cp kmjui.rc $HOME/.kde/share/apps/kmj/kmjui.rc
translate
cd $srcdir
#valgrind --trace-children=yes python kmj.py
#python kmj.py
