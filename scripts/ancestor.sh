# bash script to find ancestor(s) of a given file
# Usage: ./ancestor.sh <code_id>

# code_id and its parameters are printed as on lines 54 and 106

# Check if the code_id is provided
if [ $# -ne 1 ]
then
    echo "Usage: ./ancestor.sh <code_id>"
    exit 1
fi

mkdir -p metadata

echo "Ancestor Code,Physical,Logical" > metadata/prim_anctab.csv
echo "Ancestor Code,Physical,Logical " > metadata/sec_anctab.csv

# function to find all ancestors of a given code_id and store them in metadata/sec_anctab.csv file
# Usage: ancestors <code_id>
# code_id and its parameters are printed as on line 53
function ancestors(){

    if [[ $# -eq 1 ]]
    then
        # check if code_id_table file exists
        if [[ ! -s ./metadata/code_id_tab ]]
        then
            grep -rH -F 'code_id' | grep -Fv -- '- code_id' | grep -F ':code_id: ' > metadata/code_id_tab
            sed 's|metadata/code_id_tab:||g' metadata/code_id_tab > metadata/backup
            mv metadata/backup metadata/code_id_tab
        fi

        # store the name of the file corresponding to the code_id
        file_name=$(grep -F ":code_id: $1" metadata/code_id_tab | grep -m1 "$1\$" | cut -d ':' -f 1)

        #check if the file exists
        if [[ ! -s $file_name ]]
        then
            echo "File with code_id $1 does not exist"
            exit 1
        fi

        # get physical parameters of the file
        physical_prm=$(awk '/physical:/,/logical/||/^$/' $file_name| grep -Fv "logical:" | grep -Fv "#" | sed -e 's/physical: //'| tr -d '\n' | tr -s '[:blank:]' ';')

        #store the physical parameters with semi-colon as delimiter
        logical_prm=$(awk '/logical:/,/^$/' $file_name| grep -Fv "parents:" | grep -Fv "#" |  sed -e 's/logical: //'| tr -d '\n' | tr -s '[:blank:]' ';')

        # check if a code_id and it's ancestors are already printed and exit if yes
        if ! grep -Fxq "$1,$physical_prm,$logical_prm" metadata/sec_anctab.csv
        then

            # print the code_id and its physical and logical parameters
            echo $1,$physical_prm,$logical_prm >> metadata/sec_anctab.csv

            # get the ancestors of the code_id
            ancestors=$(awk '/parents:/,/cousins/' $file_name| grep -F -- "- code_id: " | grep -Fv "#" | cut -d ':' -f 2 )

            # make a list of ancestors from the string by separating them by space
            ancestors_list=($ancestors)

            # iterate through the list of ancestors
            for ancestor in "${ancestors_list[@]}"
            do
                ancestors $ancestor
            done
        fi

    fi
}

# function to find primary ancestor of a given code_id and store them in metadata/prim_anctab.csv file
# Usage: prim_ancestors <code_id>
# code_id and its parameters are printed as on line 104
function prim_ancestors(){
    if [[ $# -eq 1 ]]
    then

        if [[ ! -s ./metadata/code_id_tab ]]
        then
            grep -rH -F 'code_id' | grep -Fv -- '- code_id' | grep -F ':code_id: ' > metadata/code_id_tab
            sed 's|metadata/code_id_tab:||g' metadata/code_id_tab > metadata/backup
            mv metadata/backup metadata/code_id_tab
        fi

        # store the name of the file corresponding to the code_id
        file_name=$(grep -F ":code_id: $1" metadata/code_id_tab | grep -m1 "$1\$" | cut -d ':' -f 1)

        #check if the file exists
        if [[ ! -s $file_name ]]
        then
            echo "File with code_id $1 does not exist"
            exit 1
        fi

        # get physical parameters of the file
        physical_prm=$(awk '/physical:/,/logical/||/^$/' $file_name| grep -Fv "logical:" | grep -Fv "#" | sed -e 's/physical: //'| tr -d '\n' | tr -s '[:blank:]' ';')

        #store the physical parameters with semi-colon as delimiter
        logical_prm=$(awk '/logical:/,/^$/' $file_name| grep -Fv "parents:" | grep -Fv "#" |  sed -e 's/logical: //'| tr -d '\n' | tr -s '[:blank:]' ';')

        # check if a code_id and it's ancestors are already printed and exit if yes
        if ! grep -Fxq "$1,$physical_prm,$logical_prm" metadata/prim_anctab.csv
        then
            # print the code_id and its physical and logical parameters
            echo $1,$physical_prm,$logical_prm >> metadata/prim_anctab.csv

            # get the ancestors of the code_id
            ancestors=$(awk '/parents:/,/cousins/' $file_name| grep -F -- "- code_id: " | grep -Fv "#" | cut -d ':' -f 2 )

            # make a list of ancestors from the string by separating them by space
            ancestors_list=($ancestors)
            # consider only the primary ancestor and recursively call the function
            prim_ancestors ${ancestors_list[0]}
        fi
    fi

}

# Functions to print the table
# Reference: https://github.com/gdbtek/linux-cookbooks/blob/master/libraries/util.bash

function printTable()
{
    local -r delimiter="${1}"
    local -r data="$(removeEmptyLines "${2}")"

    if [[ "${delimiter}" != '' && "$(isEmptyString "${data}")" = 'false' ]]
    then
        local -r numberOfLines="$(wc -l <<< "${data}")"

        if [[ "${numberOfLines}" -gt '0' ]]
        then
            local table=''
            local i=1

            for ((i = 1; i <= "${numberOfLines}"; i = i + 1))
            do
                local line=''
                line="$(sed "${i}q;d" <<< "${data}")"

                local numberOfColumns='0'
                numberOfColumns="$(awk -F "${delimiter}" '{print NF}' <<< "${line}")"

                # Add Line Delimiter

                if [[ "${i}" -eq '1' ]]
                then
                    table="${table}$(printf '%s#+' "$(repeatString '#+' "${numberOfColumns}")")"
                fi

                # Add Header Or Body

                table="${table}\n"

                local j=1

                for ((j = 1; j <= "${numberOfColumns}"; j = j + 1))
                do
                    table="${table}$(printf '#| %s' "$(cut -d "${delimiter}" -f "${j}" <<< "${line}")")"
                done

                table="${table}#|\n"

                # Add Line Delimiter

                if [[ "${i}" -eq '1' ]] || [[ "${numberOfLines}" -gt '1' && "${i}" -eq "${numberOfLines}" ]]
                then
                    table="${table}$(printf '%s#+' "$(repeatString '#+' "${numberOfColumns}")")"
                fi
            done

            if [[ "$(isEmptyString "${table}")" = 'false' ]]
            then
                echo -e "${table}" | column -s '#' -t | awk '/^\+/{gsub(" ", "-", $0)}1'
            fi
        fi
    fi
}

function removeEmptyLines()
{
    local -r content="${1}"

    echo -e "${content}" | sed '/^\s*$/d'
}

function repeatString()
{
    local -r string="${1}"
    local -r numberToRepeat="${2}"

    if [[ "${string}" != '' && "${numberToRepeat}" =~ ^[1-9][0-9]*$ ]]
    then
        local -r result="$(printf "%${numberToRepeat}s")"
        echo -e "${result// /${string}}"
    fi
}

function isEmptyString()
{
    local -r string="${1}"

    if [[ "$(trimString "${string}")" = '' ]]
    then
        echo 'true' && return 0
    fi

    echo 'false' && return 1
}

function trimString()
{
    local -r string="${1}"

    sed 's,^[[:blank:]]*,,' <<< "${string}" | sed 's,[[:blank:]]*$,,'
}

# call the prim_ancestors function with the given code_id for storing the primary ancestors
prim_ancestors $1
# call the ancestors function with the given code_id for storing all the ancestors
ancestors $1
# command to remove the primary ancestors from ancestors to get the secondary ancestors
awk 'NR == FNR { list[tolower($0)]=1; next } { if (! list[tolower($0)]) print }' metadata/prim_anctab.csv metadata/sec_anctab.csv > metadata/sec_anctab2.csv
mv metadata/sec_anctab2.csv metadata/sec_anctab.csv
# print the primary and secondary ancestors
echo "Primary Ancestors"
printTable ',' "$(cat metadata/prim_anctab.csv)"
echo "Secondary Ancestors"
printTable ',' "$(cat metadata/sec_anctab.csv)"
