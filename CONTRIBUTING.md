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


## Main steps to contribute

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

Ask us! And thanks again for your interest in contributing to the zoo.


[eczooemail]: mailto:errorcorrectionzoo@XXXXXX?subject=code%20data&body=Please%20replace%20'@XXXXXX'%20in%20the%20email%20address%20by%20'@gmail.com'.%20Thanks%20for%20your%20message!

[eczooflm]: https://github.com/errorcorrectionzoo/eczoo_sitegen/blob/main/flm_howto.md

[eczooedit]: https://errorcorrectionzoo.org/edit_code

[atomurl]: https://atom.io/

[cc-by-sa-license]: https://creativecommons.org/licenses/by-sa/4.0/
