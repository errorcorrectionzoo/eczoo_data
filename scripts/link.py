#!/usr/bin/env python3.11
"""Script for attaching links to code, found in `main()` below.

Intended usage:
```bash
> ./link_codes.py                                       # load yaml files from `../codes/`, and search `../codes/`
> ./link_codes.py --codes_path /home/feynman/codes/     # load yaml files from custom path, and search there

# load yaml files from custom path, and search a separate custom path
> ./link_codes.py --codes_path=/home/feynman/codes/ --search_path=/home/woit/codes_to_update/
```

"""

import sys
import os
import argparse
import ruamel.yaml


def print_error(msg: str) -> None:
    """Prints error message in red"""
    color_code_ERROR = '\033[91m'
    color_code_END = '\033[0m'
    print(color_code_ERROR + msg + color_code_END)

def search_and_replace(code_name: str, code_id: str, msg: str, file_path: str) -> (str, bool, bool):
    """Search for `code_name` in `msg`, and prompt the user for replacement.

    Searches `msg` for `code_name`. If such a substring exists, prompts the user
    for replacement. Returns the updated string, and two booleans: the first for if a
    replaacement was made, and the second for if to terminate searching.

    Args:
        code_name: The string to look for in `code_id`. Despite the name, corresponds to
    the value of yaml mapping with key `name` or `short_name`.
        code_id: The id for this `code_name`.
        msg: The string to search for replacements.
        file_path: The file we're modifying

    Returns:
        A tuple whose second element indicates if replacement took place. `True` if
    replacement; else, `False`.
        The third element indicates if searching should terminate. `True` if to stop;
    else, `False`.
        If a replacement didn't take place, then the first element is simply the unmodified
    `msg`. Else, the modified `msg` is returned.

    E.g.
    ```python
    # No match!
    search_and_replace("gb", "generalized_bicycle", "Testing")  ->  ("Testing", False, False)

    # The user replaced, but wants to continue
    search_and_replace("gb", "generalized_bicycle", "As in a gb code")  ->  ("As in a \hyperref[code:generalized_bicycle]{gb} code", True, False)

    # The user decided not to replace, and continue
    search_and_replace("gb", "generalized_bicycle", "user_id: over_9000_gb")  ->  ("user_id: over_9000_gb", False, False)

    # The user decided not to replace and quit
    search_and_replace("gb", "generalized_bicycle", "user_id: over_9000_gb")  ->  ("user_id: over_9000_gb", False, True)
    ```
    """
    # codes for printing in color
    color_code_YELLOW = '\033[93m'
    color_code_CYAN = '\033[96m'
    color_code_END = '\033[0m'
    # Any matches? (not case sensitive)
    if code_name not in msg.lower():
        return (msg, False, False)
    n_matches = msg.lower().count(code_name)

    # For each possible substring, prompt the user
    # If there are spaces, as in a `short_name`, then we need to consider an offset.
    # E.g. we want to replace ` quantum ` in `I love quantum comp` with `I love \hyperref[code:quantum_code]{quantum} comp`,
    # not `I love\hyperref[code:quantum_code]{ quantum }comp`.
    has_leading_space = True if code_name[0] == ' ' else False
    has_trailing_space = True if code_name[len(code_name) - 1] == ' ' else False
    left_offset = 0 if not has_leading_space else 1
    right_offset = 0 if not has_trailing_space else -1

    last_match_idx = 0
    updated_data = False
    for _ in range(n_matches):
        match_idx = msg.lower().index(code_name, last_match_idx)
        last_match_idx = match_idx + 1

        # Let's first check if we're double-replacing
        hyperref_str = '\hyperref[code:' + code_id + ']{'
        if (match_idx >= len(hyperref_str)) and (msg[:match_idx][-len(hyperref_str):] == hyperref_str):
            continue
        # in our possible replacement, honor case and spacing
        hyperref_str += msg[(match_idx + left_offset):(match_idx + len(code_name) + right_offset)] + '}'

        # Prompt the user
        prompt_str = file_path + ':\n'
        prompt_str += 'Replace \"' + color_code_YELLOW + code_name + color_code_END + '\" in \"' + \
            color_code_YELLOW + msg[max(match_idx - 20, 0):(match_idx + len(code_name) + 20)] + color_code_END + \
            '\" using id ' + color_code_CYAN + code_id + color_code_END + '? [Y/n/q]\n'
        user_response = input(prompt_str).lower()

        if user_response != 'y' and user_response != 'yes' and user_response != 'q':
            continue
        elif user_response == 'q':
            return (msg, updated_data, True)

        # Remove the code name first, replace, and adjust index
        updated_data = True
        msg = msg[:(match_idx + left_offset)] + msg[(match_idx + len(code_name) + right_offset):]
        msg = msg[:(match_idx + left_offset)] + hyperref_str + msg[(match_idx + left_offset):]
        last_match_idx += len(hyperref_str) - 1 - (left_offset + right_offset)

    return (msg, updated_data, False)

def search_and_replace_short_name(code_name: str, code_id: str, msg: str, file_path: str) -> (str, bool, bool):
    """Search for the short name `code_name` in `msg`, and prompt the user for replacement.

    In the special case where we replace a `short_name`, to decrease the amount of false
    positives, only prompt the user if the code name is surrounded by either a dash or space.

    See:
        - `search_and_replace(str, str, str) -> (str, bool, bool)` above
    """
    replaced_short_name = False
    need_to_terminate = False

    msg, replaced_short_name, need_to_terminate = search_and_replace(' ' + code_name + ' ', code_id, msg, file_path)
    if need_to_terminate:
        return (msg, replaced_short_name, True)

    msg, replacement_made, need_to_terminate = search_and_replace('-' + code_name + ' ', code_id, msg, file_path)
    replaced_short_name |= replacement_made
    if need_to_terminate:
        return (msg, replaced_short_name, True)

    msg, replacement_made, need_to_terminate = search_and_replace(' ' + code_name + '-', code_id, msg, file_path)
    replaced_short_name |= replacement_made
    if need_to_terminate:
        return (msg, replaced_short_name, True)

    msg, replacement_made, need_to_terminate = search_and_replace('-' + code_name + '-', code_id, msg, file_path)
    replaced_short_name |= replacement_made

    return (msg, replaced_short_name, need_to_terminate)


def main(args) -> int:
    """Attaches links to codes upon prompt.

    For users:

    This script accepts a path to a directory containing error correcting codes (`--codes_path`)
    as either '.yml' or '.yaml' files. The dictionary of `code_name` and `code_id` values
    is populated from these files.

    Non-yaml files in the directory are ignored.
    This argument defaults to "../codes/". Possible usage:
    ```bash
    > ./link_codes.py
    > ./link_codes.py --codes_path=/home/feynman/codes/
    ```

    It also accepts a path to a directory of yaml files to update (`--search_path`).
    If not included, this argument defaults to the value of `--codes_path`, which
    itself defaults to `../codes/`. Possible usage:
    ```bash
    > ./link_codes.py --codes_path=/home/feynman/codes/ --search_path=/home/woit/codes_to_update/
    ```

    For developers:

    This script first populates a dictionary of error correcting code names to
    code ids (respectively the `name` and `code_id` keys in each yaml file).
    Short names are also added if present. Else, the short name is set to
    the code name with the "code" suffix removed, e.g. "psk c-q code" is
    given short name "psk c-q".

    Then, each yaml file is parsed. If it contains a substring containing _any_
    name or short name in the dictionary, the user is asked if a replacement
    should occur. If so, the file is updated.

    """
    # Check valid pathing
    if not args.search_path:
        args.search_path = args.codes_path
    if not os.path.isdir(args.codes_path) or not os.path.isdir(args.search_path):
        print_error('Error: ' + args.codes_path + ' not a valid directory!')
        return 1

    #
    #   Populating our map of names to `code_id`
    #

    # Map of `name` and `short_name` yaml keys to `code_id`
    # Keys are in lower-case since replacement isn't case-sensitive
    code_mp = {}
    # A hash set of `short_name` mappings. When iterating through `code_mp` to
    # check for substring matches in a yaml file, if a `code_mp` entry is a `short_name`
    # (as indicated by `cached_short_names` membership), then only replace a `short_name`
    # if surrounded by either a dash or space. E.g.
    # ```txt
    # Looking for "rm" in " information"?           ->  Don't ask user
    # Looking for "shor" in "Shor's algorithm"?     ->  Don't ask user
    # Looking for "gb" in "such a GB code"?         ->  Ask user for replacement
    # ```
    cached_short_names = set()
    print("Collecting yaml code data...", end='', flush=True)
    for root, dirs, files in os.walk(args.codes_path):
        for file_name in files:
            if (file_name[-3:] != 'yml' and file_name[-4:] != 'yaml'):
                continue

            file_path = os.path.join(root, file_name)
            with open(file_path, 'r') as f:
                yml_dat = ruamel.yaml.load(f, Loader=ruamel.yaml.RoundTripLoader)
                code_mp[yml_dat['name'].lower()] = yml_dat['code_id']

                if 'short_name' in yml_dat:
                    short_name = yml_dat['short_name'].lower()
                    code_mp[short_name] = yml_dat['code_id']
                    cached_short_names.add(short_name)
                else:
                    orig_str = yml_dat['name'].lower()
                    short_name = orig_str[:-5] if orig_str.endswith(' code') else orig_str
                    code_mp[short_name] = yml_dat['code_id']
                    cached_short_names.add(short_name)
    print('Done!')

    #
    #   Updating codes
    #
    print('Updating codes...', flush=True)
    for root, dirs, files in os.walk(args.search_path):
        for file_name in files:
            if (file_name[-3:] != 'yml' and file_name[-4:] != 'yaml'):
                continue

            # If flipped to true, write `yml_dat`. `yml_dat` is declared here
            # since we populate on file read, update it on file read, and dump
            # it on file write
            need_to_update_file = False
            need_to_terminate = False
            yml_dat = {}
            file_path = os.path.join(root, file_name)
            with open(file_path, 'r') as f:
                yml_dat = ruamel.yaml.load(f, Loader=ruamel.yaml.RoundTripLoader)

                # Save our code names to avoid self-replacement!
                code_name = yml_dat['name'].lower()
                code_short_name = code_name[:-5] if code_name.endswith(' code') else code_name
                if 'short_name' in yml_dat:
                    code_short_name = yml_dat['short_name'].lower()

                # `pairs` is treated as a stack. Although initially a list of
                # elements that are key, value pairs for `yml_dat`, the elements
                # are updated until `element[0]` is a list of keys in `yml_dat`
                # that map to a string `element[1]`. That string is then checked
                # for a substring.
                #
                # For example, suppose
                # ```
                # Loop 1:
                # ele = ("relations", {"parents" : [{"code_id"} : "quantum_bpsk"}]})
                # Loop 2:
                # ele = (["relations", "parents"] , [{"code_id"} : "quantum_bpsk"}])
                # Loop 3:
                # ele = (["relations", "parents", 0] , {"code_id"} : "quantum_bpsk"})
                # Loop 4:
                # ele = (["relations", "parents", 0, "code_id"] , "quantum_bpsk")
                # ```
                #
                # In the above example, if we want to make a replacement, then we can
                # update the original map by unwinding the list:
                # ```python
                # yml_dat["relations"]["parents"][0]["code_id"] = "\hyperref[code:quantum_bpsk]{quantum bpsk}"
                # ```
                # If changed by the user, this `yml_dat` is written back.
                #
                pairs = list(yml_dat.items())
                while len(pairs) != 0:
                    key, val = pairs.pop()

                    # If a string, convert our key to a list so we can append further keys
                    if type(key) is not list:
                        if key == 'code_id' or key == 'name' or key == 'short_name':
                            continue
                        key = [key,]

                    if type(val) is list:
                        # We want to be able to update our original dictionary again, so
                        # append the numeric index values to our list of keys
                        for idx in range(len(val)):
                            pairs.append( (key + [idx], val[idx]) )
                    elif type(val) is dict:
                        # We want to be able to update our original dictionary again, so
                        # append the keys of `val` to our list, whose last element
                        # is the corresponding key mapping to `val`
                        for k, v in val.items():
                            pairs.append( (key + [k], v) )
                    elif type(val) is str:
                        need_to_update_data = False
                        # Iterate through our cached dictionary of codes, checking for substrings
                        for cached_code_name, cached_code_id in code_mp.items():
                            # We don't want to self-replace!
                            if cached_code_name == code_name or cached_code_name == code_short_name:
                                continue
                            # We don't want to replace any `code_id` keys!
                            if type(key) is list and key[-1] == 'code_id':
                                continue
                            # Are looking for a `short_name`?
                            if cached_code_name in cached_short_names:
                                val, updated_data, need_to_terminate = search_and_replace_short_name(cached_code_name, cached_code_id, val, file_path)
                                need_to_update_data |= updated_data
                            else:
                                val, updated_data, need_to_terminate = search_and_replace(cached_code_name, cached_code_id, val, file_path)
                                need_to_update_data |= updated_data

                            if need_to_terminate:
                                break
                        if need_to_update_data:
                            need_to_update_file = True
                            if len(key) == 1:
                                yml_dat[key[0]] = val
                            else:
                                yml_dat_copy = yml_dat
                                # retrieve path to value
                                n_keys = len(key) - 1
                                for i in range(n_keys):
                                    yml_dat_copy = yml_dat_copy[key[i]]
                                yml_dat_copy[key[n_keys]] = val
                        if need_to_terminate:
                            break
            if need_to_update_file:
                with open(file_path, 'w') as f:
                    ruamel.yaml.dump(yml_dat, f, Dumper=ruamel.yaml.RoundTripDumper)
            if need_to_terminate:
                print('Terminating Early.')
                return 0
    return 0

def parse_arguments(argv):
    parser = argparse.ArgumentParser()
    # dir path to populate codes from
    parser.add_argument('--codes_path', type=str, default='../codes/')
    # dir path to update codes from 
    parser.add_argument('--search_path', type=str, default=None)
    return parser.parse_args()

if __name__ == '__main__':
    sys.exit(main(parse_arguments(sys.argv[1:])))
