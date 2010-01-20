#!/bin/sh

# this file is only meant for the developer, please adapt
# to your environment. Helps in translation to german.

translateMsg() {
	cd $HOME/src/kde/l10n-kde4/de/messages/playground-games
	svn up  # we want the current kmj.po
	svn cat svn://anonsvn.kde.org/home/kde/trunk/l10n-kde4/templates/messages/playground-games/kmj.pot>kmj.pot
	msgmerge --update --previous kmj.po kmj.pot
	lokalize kmj.po
	rm kmj.pot

}

translateDoc() {
	cd $HOME/src/kde/l10n-kde4/documentation/playground-games/kmj
	svn up  # we want the current index.docbook
	cd $HOME/src/kde/l10n-kde4/de/docmessages/playground-games
	svn up  # we want the current kmj.po
	svn cat svn://anonsvn.kde.org/home/kde/trunk/l10n-kde4/templates/docmessages/playground-games/kmj.pot>kmj.pot
	msgmerge --update --previous kmj.po kmj.pot
	lokalize kmj.po
	rm kmj.pot

# generate translated index.docbook
	cd $HOME/src/kde/l10n-kde4
	scripts/update_xml --nodelete de kmj
}

install() {
	cd $HOME/src/kde/l10n-kde4/de/messages/playground-games
	msgfmt -o kmj.mo kmj.po
	sudo cp kmj.mo /usr/share/locale/de/LC_MESSAGES
	rm kmj.mo
	cd $HOME/src/kde/l10n-kde4/de/docs/playground-games/kmj/
	sudo cp -a * /usr/share/doc/kde/HTML/de/kmj
}

checkXML $HOME/src/kde/playground/games/doc/kmj/index.docbook
cd $HOME/src/kde/playground/games/kmj/src
for i in *.ui
do
	pyuic4 $i > ${i%.ui}_ui.py
done
cp kmjui.rc $HOME/.kde/share/apps/kmj/kmjui.rc
translateMsg
translateDoc
install

#valgrind --trace-children=yes python kmj.py
#python kmj.py
