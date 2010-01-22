#!/bin/sh

# this file is only meant for the developer, please adapt
# to your environment. Helps in translation to german.

translateMsg() {
	cd $HOME/src/kde/l10n-kde4/de/messages/playground-games
	svn up  # we want the current kajongg.po
	svn cat svn://anonsvn.kde.org/home/kde/trunk/l10n-kde4/templates/messages/playground-games/kajongg.pot>kajongg.pot
	msgmerge --update --previous kajongg.po kajongg.pot
	lokalize kajongg.po
	rm kajongg.pot

}

translateDoc() {
	cd $HOME/src/kde/l10n-kde4/documentation/playground-games/kajongg
	svn up  # we want the current index.docbook
	cd $HOME/src/kde/l10n-kde4/de/docmessages/playground-games
	svn up  # we want the current kajongg.po
	svn cat svn://anonsvn.kde.org/home/kde/trunk/l10n-kde4/templates/docmessages/playground-games/kajongg.pot>kajongg.pot
	msgmerge --update --previous kajongg.po kajongg.pot
	lokalize kajongg.po
	rm kajongg.pot

# generate translated index.docbook
	cd $HOME/src/kde/l10n-kde4
	scripts/update_xml --nodelete de kajongg
}

install() {
	cd $HOME/src/kde/l10n-kde4/de/messages/playground-games
	msgfmt -o kajongg.mo kajongg.po
	sudo cp kajongg.mo /usr/share/locale/de/LC_MESSAGES
	rm kajongg.mo
	cd $HOME/src/kde/l10n-kde4/de/docs/playground-games/kajongg/
	sudo cp -a * /usr/share/doc/kde/HTML/de/kajongg
}

checkXML $HOME/src/kde/playground/games/doc/kajongg/index.docbook
cd $HOME/src/kde/playground/games/kajongg/src
for i in *.ui
do
	pyuic4 $i > ${i%.ui}_ui.py
done
cp kajonggui.rc $HOME/.kde/share/apps/kajongg/kajonggui.rc
translateMsg
translateDoc
install

#valgrind --trace-children=yes python kajongg.py
#python kajongg.py
