#!/bin/sh

translate() {
# http://www.gnu.org/software/autoconf/manual/gettext/xgettext-Invocation.html
# http://api.kde.org/4.0-api/kdelibs-apidocs/kdecore/html/classKLocalizedString.html

# extract messages from *.py
	xgettext -ci18n --from-code=UTF-8 --language=Python -k \
		-kki18n:1 -ki18n:1 -ki18nc:1c,2 -ki18np:1,2 \
		-ki18ncp:1c,2,3 -ktr2i18n:1 \
		-kI18N_NOOP:1 -kI18N_NOOP2:1c,2 \
		-kaliasLocale -kki18n:1 -kki18nc:1c,2 -kki18np:1,2 -kki18ncp:1c,2,3 \
		--no-wrap --msgid-bugs-address=wolfgang@rohdewald.de -ol10n/kmj.pot *.py

# merge new strings from kmj.pot into the language specific *.po:
	cd l10n
	catalogs=`find . -name '*.po'`
	for cat in $catalogs; do
		msgmerge -o $cat.new $cat kmj.pot
		mv $cat.new $cat
	done

# translate
	lokalize *.po

# compile and install the message files
	msgfmt -o de.mo de.po
	cp -a de.mo /home/wr/.kde/share/locale/de/LC_MESSAGES/kmj.mo
	cd ..
}


#

for i in *.ui
do
	pyuic4 $i > ${i%.ui}_ui.py
done
#pyrcc4 kmj.qrc >kmj_rc.py
translate
#valgrind --trace-children=yes python kmj.py
python kmj.py
