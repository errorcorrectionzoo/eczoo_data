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


## LaTeX-inspired mini-language in text

In text fields, you can make use of the following LaTeX-inspired
features:

  - Equations can be written as `\( ... \)`, they will be rendered into
    pretty formulas using MathJaX. You can use standard LaTeX math
    commands in equations, as supported e.g. by AMS-TeX (`\sim`,
    `\langle`, etc.)

  - Cite relevant papers by their arXiv number as `\cite{arxiv:XXXX.XXXXX}` or
    `\cite{arxiv:quant-ph/XXXXXXX}`, or using their DOI as
    `\cite{doi:10.ZZZZZZ}`.  Citations can be combined as in LaTeX:
    `\cite{arxiv:XXX,arxiv:YYY,doi:ZZZ}`.  If there is neither an arxiv number nor a DOI
    number available, you can enter a citation manually as `\cite{manual:{(enter
    citation line incl. author and year here)}}` (you can use latex-like
    commands like `\emph{..}` and `\textbf{..}` within the manual citation text).
    
  - Reference other codes using `\ref{code:<other-code-id>}`.  To set a custom
    label to show, you can use `\hyperref[code:<other-code-id>]{link text}`.
    
  - Insert hyperlinks to other web pages as
    `\href{https://example.com/example/page}{shown link text}` or with
    `\url{https://example.com/example/page}`.
    
  - Input accents, special characters, etc., directly as Unicode (files
    are encoded in UTF-8): `éàààé😅Á`
    
  - Protect characters that have a special meaning using the following
    macros: `\textbackslash` (backslash character), `\ ` (force space),
    `\{` (open brace), `\}` (closing brace), `\%` (percent character).
    
  - The macros `\emph{...}`, `\textit{...}`, and `\textbf{...}` can be
    used for italic or for bold text.
  
  - You can insert footnotes with `\footnote{...}`.  Footnotes should
    be avoided in general.


## Building and previewing the site

To build the site, follow the instructions given in the [`eczoo_generator`
repository](https://github.com/errorcorrectionzoo/eczoo_generator).


## Contributing

Get in touch with Victor V Albert & feel free to submit pull requests!
