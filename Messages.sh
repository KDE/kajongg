#!/bin/sh
# https://www.gnu.org/software/gettext/manual/html_node/gettext-Invocation.html#gettext-Invocation
# https://api.kde.org/frameworks/ki18n/html/prg_guide.html
# extract messages from *.py

# currently, the .pot lives at
# https://websvn.kde.org/trunk/l10n-kf5/templates/messages/kajongg/kajongg.pot

${EXTRACTRC:-extractrc} src/*.rc >> rc.cpp

${XGETTEXT:-xgettext} \
		-ci18n --from-code=UTF-8 --language=Python -k \
		-ki18n:1 -ki18nc:1c,2 -ki18np:1,2 \
                -ki18nE:1 -ki18ncE:1c,2 \
		-ki18ncp:1c,2,3 -ktr2i18n:1 \
		-kI18N_NOOP:1 -kI18N_NOOP2:1c,2 \
		-kaliasLocale \
		-kcreateRule:1 \
		--no-wrap --msgid-bugs-address=wolfgang@rohdewald.de -o${podir:-.}/kajongg.pot \
		rc.cpp `find . -name \*.py`
