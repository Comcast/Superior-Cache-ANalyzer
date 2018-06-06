#!/bin/bash

lintResults="$(pylint --rcfile='./.pylintrc' scan/ 2>/dev/null)"
score=$(echo "$lintResults" | grep 'Your code has been rated at' | sed -r 's/[ a-zA-Z]//g' | cut -d '/' -f1)

if [[ -z "$score" || $(echo "$score<9.50" | bc -l) -ne 0  ]]; then
	echo "$lintResults" >&2
	exit 1
fi

echo "$lintResults"

if [[ ! -z "$(which git 2>/dev/null)" && ! -z "$(which cc 2>/dev/null)" && ! -z "$(which autoreconf 2>/dev/null)" && ! -z "$(which make 2>/dev/null)" ]]; then
	if [[ -d ats_test ]]; then
		echo "Warning! removing existing 'ats_test' directory..." >&2
		sleep 3 # Plenty of time to hit ^C
		rm -rf ats_test
	fi

	git clone https://github.com/apache/trafficserver.git ats_test
	pushd >/dev/null ats_test
	git checkout 7.1.x

	autoreconf -if || { echo "'autoreconf' has failed." >&2; exit 2; }

	mkdir goal

	./configure --prefix "$(pwd)/goal" || { echo "'./configure' has failed." >&2; exit 2; }

	make -j || { echo "'make' has failed." >&2; exit 2; }

	make install || { echo "'make install' has failed." >&2; exit 2; }

	for i in $(ls -A); do
		case $i in
			goal | tests )
				;;
			* )
				rm -rf "$i";
				;;
		esac
	done

	mkdir -p "tests/gold_tests/scan/gold"

	cp "../tests/scan.test.py" "tests/gold_tests/scan/"
	cp "../tests/cache_populated.gold" "tests/gold_tests/scan/gold/"

	tests/autest.sh --ats-bin goal/bin --show-color -f scan || { echo "Autests failed..." >&2; exit 2; }

else
	echo "Cannot run autests, need git, make, autoconf and a C compiler (and ATS dependencies)" >&2
fi

# tests/test.py

# if [[ $? -ne 0 ]]; then
# 	exit 1
# fi

