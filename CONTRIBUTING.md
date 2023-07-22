# Thanks for contributing to the Error Correction Zoo!

Your contribution to expanding and improving the Error Correction Zoo is very
welcome.

## How to contribute content

You can contribute by opening sending us an [email][eczooemail], opening an
issue, or sending us a pull request.

The content of the Zoo is entered in structured form in YAML files.  Each
error-correcting code has a corresponding YAML file in the `codes/` folder.  You
can contribute content for the zoo by sending us pull requests for new YAML
files or expanding on existing ones. If you prefer to avoid using git, you can
also send us your new YAML code files [by email][eczooemail].

Use the [Error Correction Zoo's own code information editor][eczooedit] so you
don't have to edit YAML code directly.  If you edit YAML files directly, please
make sure you understand the YAML file syntax and use an appropriate text editor
to avoid YAML syntax errors (such as [Atom][atomurl]).


## Please take note:

- Use [LaTeX-like formatting minilanguage][eczooflm] features to write math,
  links, enumeration lists, headers, etc. Use markup sparingly, when it will
  help the reader understand the content; don't abuse it.

- Content should be thoroughly cross-referenced with citations and links to
  codes that you might mention. Check the [LaTeX-like formatting minilanguage
  howto][eczooflm] for details.

- All Zoo content is distributed under the [CC-BY-SA License][cc-by-sa-license].

- When submitting contributions with edited YAML files, make sure you update the
  file's change log (in the `_meta:` field) to include your user ID and
  contribution date (approximate).  If you don't have a user ID yet, create one
  in `users/users_db.yml` in your pull request.  Only significant edits count
  in the change log; fixing typos and formatting are not recorded.

## Questions?

Ask us! And thanks again for your interest in contributing.


[eczooemail]: mailto:errorcorrectionzoo@XXXXXX?subject=code%20data&body=Please%20replace%20'@XXXXXX'%20in%20the%20email%20address%20by%20'@gmail.com'.%20Thanks%20for%20your%20message!

[eczooflm]: https://github.com/errorcorrectionzoo/eczoo_sitegen/blob/main/flm_howto.md

[eczooedit]: https://errorcorrectionzoo.org/edit_code

[atomurl]: https://atom.io/

[cc-by-sa-license]: https://creativecommons.org/licenses/by-sa/4.0/
