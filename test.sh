#!/bin/bash

lintResults="$(pylint --rcfile='./.pylintrc' scan/ 2>/dev/null)"
score=$(echo "$lintResults" | grep 'Your code has been rated at' | sed -r 's/[ a-zA-Z]//g' | cut -d '/' -f1)

if [[ -z "$score" || $(echo "$score<9.50" | bc -l) -ne 0  ]]; then
	echo $lintResults >&2
	exit 1
fi

echo "$lintResults"

tests/test.py

if [[ $? -ne 0 ]]; then
	exit 1
fi

exit 0
