#!/bin/sh

# this file is only meant for the developer, please adapt
# to your environment. Helps in translation to german.

translateMsg() {
	cd $HOME/src/kde/l10n-kde4/de/messages/kdegames
	svn up  # we want the current kajongg.po
	rm -f kajongg.pot
	svn cat svn://anonsvn.kde.org/home/kde/trunk/l10n-kde4/templates/messages/kdegames/kajongg.pot>kajongg.pot
	msgmerge --update --previous kajongg.po kajongg.pot

}

translateDoc() {
	cd $HOME/src/kde/l10n-kde4/documentation/kdegames/kajongg
	svn up  # we want the current index.docbook
	cd $HOME/src/kde/l10n-kde4/de/docmessages/kdegames
	svn up  # we want the current kajongg.po
	rm -f kajongg.pot
	svn cat svn://anonsvn.kde.org/home/kde/trunk/l10n-kde4/templates/docmessages/kdegames/kajongg.pot>kajongg.pot
	msgmerge --update --previous kajongg.po kajongg.pot
	lokalize kajongg.po
	rm kajongg.pot

# generate translated index.docbook
	cd $HOME/src/kde/l10n-kde4
	scripts/update_xml --nodelete de kajongg
}

install() {
	cd $HOME/src/kde/l10n-kde4/de/messages/kdegames
	msgfmt -o kajongg.mo kajongg.po
	sudo cp kajongg.mo /usr/share/locale/de/LC_MESSAGES
	rm kajongg.mo
	cd $HOME/src/kde/l10n-kde4/de/docs/kdegames/kajongg/
	sudo cp -a * /usr/share/doc/kde/HTML/de/kajongg
}

checkXML $HOME/src/kde/kdegames/doc/kajongg/index.docbook
cd $HOME/src/gitgames/kajongg/src
cp kajonggui.rc $HOME/.kde/share/apps/kajongg/kajonggui.rc
translateMsg
translateDoc
install

#valgrind --trace-children=yes python kajongg.py
#python kajongg.py
