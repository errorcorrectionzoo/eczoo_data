# Code data for the EC zoo

This repository contains the data, in a semi-structured form, which forms the
contents of the [Error Correction Zoo](https://errorcorrectionzoo.org/).

If you find the Error Correction Zoo useful, we'd be very grateful if you cite
it!  Here's a BibTeX blurb you could use:

```bibtex
@book{ErrorCorrectionZoo,
  title={The Error Correction Zoo},
  year={2025},
  editor={Victor V. Albert and Philippe Faist},
  url={https://errorcorrectionzoo.org/}
}
```

The code meta-information is stored in YAML format, with one file per code.

Jump to:
* [What is a YAML file?](#the-zoo-data-files)
* [Supported LaTeX-inspired syntax](#latex-inspired-mini-language-syntax)
* [How to contribute content](#contributing)

## The Zoo data files

All of the zoo entries' information are stored in data files that are both
human and machine readable.

See the `template.yml` file to get started on contributing a code entry.

### The YAML language

If you type in new codes, make sure you understand the basics of the
YAML language, and be sure to use a good text editor (if you'd like
a suggestion, check out the [Atom](https://atom.io/) text editor).

YAML is a common markup language.  You can [google
"YAML tutorial"](https://google.com/search?q=YAML+tutorial) or check out
the language's [Wikipedia
page](https://en.wikipedia.org/wiki/YAML).)

**Note**: Be mindful of line indentation, as it is important in order
to obtain a well-formed and unambiguous YAML file.

### Text content in the YAML file

By convention, we store short pieces of text as single-quoted strings, e.g.:

    code_id: surface
    name: 'Kitaev''s surface code'

Single quotes within the string must be typed twice to avoid closing
the string.  Make sure your text editor doesn't automatically convert
the quotes into pretty curly quotes, which are distinct unicode
characters and will not be recognized as text string delimiters.  In
fact, you can use the pretty quote characters ``‘`` ``’`` ``“`` ``”``
within the string without having to double them.  There is no need to
escape special characters (not even ``\``).

For longer blocks of text, perhaps with multiple paragraphs and/or
display equations, we use an alternative YaML syntax for strings:

    description: |
        The description goes here.  It can span multiple
        lines, each with indentation.  Like
        LaTeX code, white space and line breaks are
        simplified to form pretty paragraphs.

        Use two line breaks to start a new paragraph, as
        we did here.

(Side note: YAML supports another style of block text, introduced
by `description: >` instead of `description: |`, which automatically
folds whitespace using certain rules that are often convenient when
typing paragraphs of text.  The use of this syntax is discouraged
because it might interfere with possible whitespace's meaning in our
LaTeX-inspired mini-language; for instance, leaving an empty line
will fail to start a new paragraph.)

## LaTeX-inspired mini-language syntax

In most text fields, you can make use of LaTeX-inspired
command syntax.  You can insert math expressions, add citations,
format text, add figures and tables, etc., using a precise
syntax with commands that is described here:
https://github.com/errorcorrectionzoo/eczoo_sitegen/blob/main/flm_howto.md

Example:

    description: |
        Text can contain some simple LaTeX macros, for instance
        for \textbf{bold text} and \emph{italic text}.

        Use two line breaks to start a new paragraph. You
        can use inline math like \(\alpha=\sum_j\beta_j\) and
        display equations like
        \begin{align}
            S_1 &= I\,X\,Z\,Z\,X\ ;  \nonumber\\
            S_2, \ldots, S_4 &= \text{cyclical permutations of \(S_1\)}\ .
            \label{eq:stabilizers}
        \end{align}

        Refer to equations with \eqref{eq:stabilizers}, etc. ...


## Contributing

Get in touch with Victor V Albert & feel free to submit pull requests!  You
can also check out our more detailed
[contributing guidelines](https://github.com/errorcorrectionzoo/eczoo_data/blob/main/CONTRIBUTING.md).

The main steps to contribute content are:

- Create a pull request with the content you'd like to propose.  Mark it as
  a "draft" so we know you're still fine-tuning it.

- Once you created the pull request, you can preview the content as you are
  proposing in your pull request by visiting:

  https://errorcorrectionzoo.org/gitpreview

  Wait until the webpage loads (it can take a couple minutes).  Then, enter
  your pull request number in the form at the bottom of the page and click
  "Go to PR!".  Select the relevant code at the top of the page to preview
  the code page as it will appear in the zoo if your PR is accepted.

  Error messages will hopefully help you identify and locate errors in
  your YAML files (e.g., invalid syntax).

- You can update your pull request to fine-tune its contents.  To refresh
  and reload the preview, you can simply hit "Go to PR!" again.

- Once you're happy with the content you're suggesting, you can mark your
  pull request as ready by removing the "draft" mention.  Victor might
  also have some suggestions for you on your pull request, so make sure
  you have your github notifications on :)


## Building and previewing the site locally

To build and preview the site locally, follow the instructions given
in the [`eczoo_sitegen`
repository](https://github.com/errorcorrectionzoo/eczoo_sitegen).


## I want to create the &lt;Your Favorite Topic&gt; Zoo. How did you build the EC Zoo and can I reuse your code?

The error correction zoo is based on [ZooDb JS library framework](https://github.com/phfaist/zoodb).  You
are welcome to use develop your own Zoo based on this library.  Consider starting with [this simple toy
example of a zoo built with ZooDb](https://github.com/phfaist/zoodb-example).

Get in touch with me! I'll be happy to point to the basic tools we used and how they
can be reused to build other zoos (contact info at https://phfaist.com/).
