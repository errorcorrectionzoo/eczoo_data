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
        
        
## LaTeX-inspired mini-language in text

In text fields, you can make use of the following LaTeX-inspired
features:

  - Leave a blank line to start a new paragraph.
    
  - The macros `\emph{...}`, `\textit{...}`, and `\textbf{...}` can be
    used for italic or for bold text.
    
  - Input accents, special characters, etc., directly as Unicode:
    `éàààé😅Á`.  (Files are always encoded in UTF-8.)  For instance,
    you can use pretty quotes ``‘`` ``’`` ``“`` ``”``; dashes ``—``
    (em dash), ``–`` (en dash, for ranges); spaces `` `` (non-breaking
    space), `` `` (em space), `` `` (thin space), etc.
    
  - Math expressions can be written as `\( ... \)`, they will be rendered
    into pretty formulas using MathJaX. You can use standard LaTeX
    math commands in equations, as supported e.g. by AMS-TeX (`\sim`,
    `\langle`, etc.).  You can also use `\bra{\phi}` and `\ket{\psi}`.
    
  - Protect characters that might have a special meaning using the
    following macros: `\textbackslash` (backslash character), `\ `
    (force a space), `\{` (open brace), `\}` (closing brace), `\%`
    (percent character), `\&` (ampersand), `\$` (dollar sign), `\#`
    (number sign).
    
  - Cite relevant papers by their arXiv number as
    `\cite{arxiv:XXXX.XXXXX}` or `\cite{arxiv:quant-ph/XXXXXXX}`, or
    using their DOI as `\cite{doi:10.ZZZZZZ}`.  *DOIs are
    automatically retrieved for `arXiv` citations, so please use
    `arXiv` identifiers whenever possible.*
    
    Citations can be combined as in LaTeX:
    `\cite{arxiv:XXX,arxiv:YYY,doi:ZZZ}`.  If there is neither an
    arxiv number nor a DOI number available, you can enter a citation
    manually as `\cite{manual:{A. Smith et al., \emph{Journal of Weird
    Stuff} 12:\textbf{A}, 1003--1592 (1943)}}`.
    
  - Reference other codes using `\ref{code:<other-code-id>}`.  To set
    a custom label to show, you can use
    `\hyperref[code:<other-code-id>]{link text}`.
    
  - Use the `\begin{align} ... \end{align}` and `\begin{gather}
    ... \end{gather}` environments for display equations, and you can
    use `\begin{split} ... \end{split}` within a display equation.
    You can use `\label{eq:...}` inside the equation environments and
    you can refer to labeled equations with `\eqref{eq:...}`.  Do not
    use ~~`(\ref{eq:...})`~~. The label must start with the prefix
    `eq:`.  You can also use `\[ ... \]` for an unnumbered display
    equations.

  - Insert hyperlinks to other web pages as
    `\href{https://example.com/example/page}{shown link text}` or with
    `\url{https://example.com/example/page}`.
  
  - You can insert footnotes with `\footnote{...}`.  Footnotes should
    be avoided in general.


For example:

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
