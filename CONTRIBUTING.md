# Contributing Guidelines
If you would like to contribute code to this project you can do so through
GitHub by forking the repository and sending a pull request.

## Pylint
Please ensure that your contribution does not cause the `pylint` score of the
package to fall below 9.5. You can check the score with

```
pylint /path/to/Superior-Cache-ANalyzer/scan/
```

You may safely ignore the following errors/warnings (by setting this in your
`~/.pylintrc` file or specifying it on the command line, but please don't
explicitly ignore these with a pylint directive in-line with the code):

* C0103
* C0326
* C0330
* C0362
* C0413
* E1300
* R0902
* R0911
* W0603
* W0612
* W1401

The rest of `pylint`'s settings should remain default except that:

* Indentations should be with **tabs only, NEVER spaces**. Spaces may be used
within an indentation level to align text.
* Line endings should be unix/line-feed (LF)/'\n' only, **don't** include any
Windows line endings (carriage-return-then-linefeed (CRLF)/'\r\n' )
* **All** files in the project **must** end with a newline (leave a blank line
at the end of the file.)

If there's a good reason you must catch a general `Exception`, state your case
in the pull request and I'll probably allow it.

## Type Hinting
Because this is such a huge, complex project, it's vital that your functions
use proper type hinting annotations for their arguments and return values.
Otherwise I will quickly be at a loss to understand my own project.
However, `self` and `cls` don't need type hints, because it's understood that
they refer to an instance and a class, respectively. For type hinting usage,
see [PEP 484](https://www.python.org/dev/peps/pep-0484/). Also, to avoid
breaking comparability with the ever-frustrating RHEL/CEntOS/Fedora family of
Linux flavors (because they refuse to update Python at any cost), please be
sure that instead of _inheriting_ from `typing.NamedTuple` you are creating
one via the explicit constructor: `MyType = typing.NamedTuple('MyType', ...)`.

Now some comcast stuff:

## CLA
---------
Before Comcast merges your code into the project you must sign the [Comcast
Contributor License Agreement
(CLA)](https://gist.github.com/ComcastOSS/a7b8933dd8e368535378cda25c92d19a).

If you haven't previously signed a Comcast CLA, you'll automatically be asked
to when you open a pull request. Alternatively, we can send you a PDF that
you can sign and scan back to us. Please create a new GitHub issue to request
a PDF version of the CLA.
