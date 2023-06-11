#!/usr/bin/env python
"""Script for attaching links to code. Found in `main()` below"""

import sys
import os
import argparse
import ruamel.yaml


def print_error(msg: str) -> None:
    """Prints error message in red"""
    color_code_ERROR = '\033[91m'
    color_code_END = '\033[0m'
    print(color_code_ERROR + msg + color_code_END)

def main(args) -> int:
    """Attaches links to codes upon prompt.

    For users:

    This script accepts a path to a directory containing error correcting codes
    as either '.yml' or '.yaml' files. Non-yaml files in the directory are ignored. 
    This argument defaults to "../codes/". Possible usage:
    ```bash
    > ./link_codes.py 
    > ./link_codes.py --codes_path=/home/feynman/codes/
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
    if (not os.path.isdir(args.codes_path)):
        print_error('Error: ' + args.codes_path + ' not a valid directory!')
        return 1

    #
    #   Populating our map of names to `code_id`
    #
    
    # Map of `name` and `short_name` yaml keys to `code_id`
    # Keys are in lower-case since replacement isn't case-sensitive
    code_mp = {}
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
                    code_mp[yml_dat['short_name'].lower()] = yml_dat['code_id']
                else:
                    short_name = yml_dat['name'].removesuffix(' code').lower()
                    code_mp[short_name] = yml_dat['code_id']
    print('Done!')

    #
    #   Updating codes
    #
    print('Updating codes...', flush=True)
    for root, dirs, files in os.walk(args.codes_path):
        for file_name in files:
            if (file_name[-3:] != 'yml' and file_name[-4:] != 'yaml'):
                continue

            # If flipped to true, write `yml_dat`. `yml_dat` is declared here
            # since we populate on file read, update it on file read, and dump
            # it on file write
            need_to_update_file = False
            yml_dat = {}
            file_path = os.path.join(root, file_name)
            with open(file_path, 'r') as f:
                yml_dat = ruamel.yaml.load(f, Loader=ruamel.yaml.RoundTripLoader)

                # Save our code names to avoid self-replacement!
                code_name = yml_dat['name'].lower()
                code_short_name = yml_dat['name'].removesuffix(' code').lower()
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
                        if key == 'code_id':
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
                            # Any matches? (not case sensitive)
                            if cached_code_name not in val.lower():
                                continue
                            n_matches = val.lower().count(cached_code_name)

                            # For each possible substring, prompt the user
                            last_match_idx = 0
                            for _ in range(n_matches):
                                match_idx = val.lower().index(cached_code_name, last_match_idx)
                                last_match_idx = match_idx + 1

                                # Let's first check if we're double-replacing
                                hyperref_str = '\hyperref[code:' + cached_code_id + ']{'
                                if (match_idx > len(hyperref_str)) and (val[:match_idx][-len(hyperref_str):] == hyperref_str):
                                    continue
                                hyperref_str += cached_code_name + '}'

                                # Prompt the user
                                prompt_str = file_path + ':\n'
                                prompt_str += 'Replace \"' + cached_code_name + '\" in \"' + val[max(match_idx - 5, 0):(match_idx + len(cached_code_name) + 5)] + '\"? [Y/n]\n'
                                user_response = input(prompt_str).lower()
                            
                                if user_response != 'y' and user_response != 'yes':
                                    continue
                                need_to_update_data = True

                                # Remove the code name first, replace, and adjust index
                                val = val[:match_idx] + val[(match_idx + len(cached_code_name)):]
                                val = val[:match_idx] + hyperref_str + val[match_idx:]
                                last_match_idx += len(hyperref_str) - 1
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
            if need_to_update_file:
                with open(file_path, 'w') as f:
                    ruamel.yaml.dump(yml_dat, f, Dumper=ruamel.yaml.RoundTripDumper)
    return 0

def parse_arguments(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('--codes_path', type=str, default='../codes/')
    return parser.parse_args()

if __name__ == '__main__':
    sys.exit(main(parse_arguments(sys.argv[1:])))
