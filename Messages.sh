#!/bin/sh
# http://www.gnu.org/software/autoconf/manual/gettext/xgettext-Invocation.html
# http://api.kde.org/4.0-api/kdelibs-apidocs/kdecore/html/classKLocalizedString.html
# extract messages from *.py

# currently, the .pot lives at 
# http://websvn.kde.org/trunk/l10n-kde4/templates/messages/playground-games/kmj.pot

${EXTRACTRC:-extractrc} *.ui *.rc > rc.cpp

${XGETTEXT:-xgettext} \
		-ci18n --from-code=UTF-8 --language=Python -k \
		-kki18n:1 -ki18n:1 -ki18nc:1c,2 -ki18np:1,2 \
		-ki18ncp:1c,2,3 -ktr2i18n:1 \
		-kI18N_NOOP:1 -kI18N_NOOP2:1c,2 \
		-kaliasLocale -kki18n:1 -kki18nc:1c,2 -kki18np:1,2 -kki18ncp:1c,2,3 \
		-kRule:1 \
		--no-wrap --msgid-bugs-address=wolfgang@rohdewald.de -o${podir:-.}/kmj.pot \
		rc.cpp `find . -name \*.py`

