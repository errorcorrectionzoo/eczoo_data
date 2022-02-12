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

In text fields, you can make use of the following LaTeX-inspired
features:

### Bold, emphasis, special characters

  - Leave a blank line to start a new paragraph.  Whitespace is
    simplified as usual in LaTeX, i.e., consecutive spaces will not
    insert more space.
    
  - The macros `\emph{...}`, `\textit{...}`, and `\textbf{...}` can be
    used for italic or for bold text.
    
  - Input accents, special characters, etc., directly as Unicode:
    `éàààé😅Á`.  Note that source files should always be encoded using
    the UTF-8 encoding.  You can use pretty quotes ``‘`` ``’`` ``“``
    ``”``; dashes ``—`` (em dash), ``–`` (en dash, for ranges); spaces
    `` `` (non-breaking space), `` `` (em space), `` `` (thin space),
    etc.
    
  - Protect characters that might have a special meaning using the
    following macros: `\textbackslash` (backslash character), `\ `
    (force a space), `\{` (open brace), `\}` (closing brace), `\%`
    (percent character), `\&` (ampersand), `\$` (dollar sign), `\#`
    (number sign).
    
### Math

  - Math expressions can be written as `\( ... \)`, they will be rendered
    into pretty formulas using MathJaX. You can use standard LaTeX
    math commands in equations, as supported e.g. by AMS-TeX (`\sim`,
    `\langle`, etc.).  You can also use `\bra{\phi}` and `\ket{\psi}`.
    
  - Use the `\begin{align} ... \end{align}` and `\begin{gather}
    ... \end{gather}` environments for display equations, and you can
    use `\begin{split} ... \end{split}` within a display equation.
    You can use `\label{eq:...}` inside the equation environments and
    you can refer to labeled equations with `\eqref{eq:...}`.  Do not
    use ~~`(\ref{eq:...})`~~. The label must start with the prefix
    `eq:`.  You can also use `\[ ... \]` for unnumbered display
    equations.

### Citations

  - Cite relevant papers by their arXiv number as
    `\cite{arxiv:XXXX.XXXXX}` or `\cite{arxiv:quant-ph/XXXXXXX}`, or
    using their DOI as `\cite{doi:10.ZZZZZZ}`.
    
    *DOIs are
    automatically retrieved for `arXiv` citations, so please use
    `arXiv` identifiers whenever possible.  If the DOI is not
    retreived correctly (e.g., it is not listed correctly on the
    arXiv page), then please add a line in the file
    `citation_extras/citation_hints.yml` (in this repo),
    specifically in the `arxiv_to_doi_override:`
    section.  You can also file an issue in this repo so that we
    take care of this addition.*
    
    Citations can be combined as in LaTeX:
    `\cite{arxiv:XXX,arxiv:YYY,doi:ZZZ}`.  If there is neither an
    arxiv number nor a DOI number available, you can enter a citation
    manually as `\cite{manual:{A. Smith et al., \emph{Journal of Weird
    Stuff} 12:\textbf{A}, 1003--1592 (1943)}}`.
    
### References to other codes and external links

  - Reference other codes using `\ref{code:<other-code-id>}`.  To set
    a custom label to show, you can use
    `\hyperref[code:<other-code-id>]{link text}`.
    
  - Insert hyperlinks to other web pages as
    `\href{https://example.com/example/page}{shown link text}` or with
    `\url{https://example.com/example/page}`.
    
  - Insert references to figures and tables with `\ref{figure:my-figure-label}`
    and `\ref{table:my-table-label}`.  In contrast to LaTeX' usual
    behavior, the output of these commands includes the words “Figure”
    or “Table”, i.e., you get *Figure X* or *Table X*.
  
  - You can insert footnotes with `\footnote{...}`.  Footnotes should
    be avoided in general.

### Figures and tables

  - At last, we have support for the float environments
    ``\begin{figure} ... \end{figure}`` and ``\begin{table}
    ... \end{table}``.  Both of these environments produce a break in
    the text (they place their content immediately), in contrast to
    their standard LaTeX implementation.  The syntax of these
    environments is as follows:
    ```
    \begin{figure}
        \includegraphics{figure_file_name}
        \caption{Your figure can have a caption}
        \label{figure:my-figure-label}
    \end{figure}
    ```

    The ``figure_file_name`` must be the name of an image file that is
    in the code YAML file tree, which is searched relative to the code
    YAML file's path.  In ``figure_file_name``, the file name
    extension (e.g., ``.svg``) can be omitted.  The preferred file
    structure for codes that have image files is to place the code
    YAML file along with the image files in their own, separate folder
    that is specific to that code.
    
    You may not specify optional sizing/trimming/cropping arguments to
    the ``\includegraphics`` command.  Please prepare your figure
    directly at the correct size.  Bear in mind that if you have text
    elements in your figure, then resizing the figure will cause a
    visual mismatch with the article text appearance.

    You may omit both ``\caption`` and ``\label`` commands to generate
    a figure without any caption.  If you specify a ``\label`` and
    omit the ``\caption`` command, a figure with the simple legend
    text “*Figure X*” will be generated.  You can also use the label
    to reference the figure from the main text with
    ``\ref{figure:my-figure-label}``.  The label prefix `figure:`
    or `table:` must match the float environment name.

    Our parser is very picky about this syntax and will issue errors
    if you deviate from it.
    
  - The preferred file format is a vector SVG file.
  
    The size at which you place elements in your SVG file is
    important.  The stated physical dimensions that are present in the
    SVG file are used to place the image at the correct size and
    resolution to match the surrounding article.  General text should
    be typeset preferably using the ‘Source Sans Pro’ at 10 point
    size, to match the typography of the surrounding article.  (You
    can place smaller or bigger text for axis markers, or use a
    different font if it's necessary, or etc.; use your good judgment
    and common sense.  We'll come back at you in case we'd prefer some
    changes.)
    
    Be sure also to set the page dimensions of your SVG document
    correctly to match the size of your graphic.  If you use Inkscape,
    you can select “File” → “Document Properties” → “Resize page to
    drawing or selection.”
    
    You can also use PNG or JPG/JPEG files.  In this case, the
    stated physical dots-per-inch or pixels-per-inch setting of the
    image, read directly from the image metadata, is honored.

  - Tables function in exactly the same way as figures, and
    furthermore, the table content must be provided as an external
    image file.  The only practical difference between a `figure`
    environment and a `table` environment is the legend *Figure X* or
    *Table X* with separate sequential numbering.
    
    We don't support the `tabular` environment.  There are simply too
    many different options and ways in which tabular features can be
    generated in LaTeX that we cannot hope to offer and maintain a
    useful inline tabular solution.
    
    You can design your table whichever way you like, either by
    creating a graphic using drawing software like Inkscape, or by
    running LaTeX on a separate file to generate the table graphic.

    You can generate your table using LaTeX as follows.  Download the
    file
     [`table_template.tex`](https://github.com/errorcorrectionzoo/eczoo_data/blob/main/table_template.tex)
    and edit it to your liking to display the desired table (search
    for "TABLE STARTS HERE").  This template needs to be compiled
    **using LuaLaTeX** instead of standard LaTeX in order to use the
    ‘Source Sans Pro’ font.
    
        > lualatex my_table.tex

    Then convert the generated PDF file into SVG, for instance using
    the `dvisvgm` utility:

        > dvisvgm --pdf my_table.pdf
        
    If you're running on Mac OS, you might need to install ghostscript
    (with [homebrew](https://brew.sh/), you can do ``brew install
    ghostscript``) and replace the *dvisvgm* call by ``dvisvgm
    --libgs=/usr/local/opt/ghostscript/lib/libgs.dylib --pdf
    my_table.pdf``
    
    If you generate your table using LaTeX, it is recommented to keep
    the source `.tex` file next to the generated `.svg` file in the
    code YAML tree, in case the table needs to be modified or
    regenerated at a later point in time.
    
    


### An example

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
