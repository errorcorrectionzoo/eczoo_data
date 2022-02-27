# Code data for the EC zoo

Code meta-information is stored in YAML format, one file per code.

## The YAML language

If you type in new codes, make sure you understand the basics of the
YaML language, and be sure to use a good text editor (if you'd like
a suggestion, check out the [Atom](https://atom.io/) text editor).

YaML is a common markup language.  You can [google
"YAML tutorial"](https://google.com/search?q=YaML+tutorial) or check out
the language's [Wikipedia
page](https://en.wikipedia.org/wiki/YAML).)


## Structure and hierarchy of the data files

See the `template.yml` file to get started.

(@VVA: feel free to fill in more info about folder structure etc. here)


## Text content in the YaML file

By convention, we store short pieces of text as single-quoted strings, e.g.:

    code_id: 'surface'
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
        
## LaTeX-inspired mini-language in text

In most text fields, you can make use of LaTeX-inspired
command syntax.  You can insert math expressions, add citations,
format text, add figures and tables, etc., using a precise
syntax with commands that is described here:
https://github.com/errorcorrectionzoo/eczoo_generator/blob/main/latexlike_minilang_howto.md

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



## Building and previewing the site

To build and preview the site locally, follow the instructions given
in the [`eczoo_generator`
repository](https://github.com/errorcorrectionzoo/eczoo_generator).


## Contributing

Get in touch with Victor V Albert & feel free to submit pull requests!
