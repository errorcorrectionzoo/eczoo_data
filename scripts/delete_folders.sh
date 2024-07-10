#!/bin/bash

# Define the list of folder names to keep
keep=(
  "3d_color"
  "488_color"
  "analog_surface"
  "arvind"
  "ball_color"
  "binomial"
  "braunstein"
  "capped_color"
  "cartier"
  "cat"
  "check_product"
  "checkerboard"
  "clifford-deformed_surface"
  "clifford_qsc"
  "constant_excitation_permutation_invariant"
  "covariant"
  "crystalline_dynamic_gen"
  "dlv"
  "ea_analog_stabilizer"
  "ea_mds"
  "eth"
  "fiber_bundle"
  "fibonacci_fractal_liquid"
  "floquet"
  "generalized_quantum_divisible"
  "gkp"
  "gkp-cluster-state"
  "galois_fqrs"
  "group_cluster_state"
  "ha_ldpc"
  "happy"
  "heavy_hex"
  "hermitian_qldpc"
  "hierarchical"
  "hh_fracton"
  "hhb_fracton"
  "homological_number-phase"
  "iterated_ramanujan"
  "kitaev_chain"
  "landau_level"
  "layer"
  "lloyd_slotine"
  "matching"
  "newman_moore"
  "niset_andersen_cerf"
  "nonabelian_covariant_erasure"
  "nonlocal_lowdepth"
  "ntru_gkp"
  "paircat"
  "penrose"
  "qlwc"
  "quantum_cyclic"
  "quantum_h"
  "quantum_hadamard_bpsk"
  "quantum_locally_recoverable"
  "quantum_pin"
  "quantum_ppm"
  "quantum_quasi_cyclic"
  "quantum_triorthogonal"
  "qubit_5_6_2"
  "qubit_9_12_3"
  "qudit_color"
  "qudit_gnu_permutation_invariant"
  "qudit_hamming_css"
  "qudit_stabilizer"
  "qutrit_golay"
  "real_projective_plane"
  "rhombic_dodecahedron_surface"
  "ruskai"
  "sparse_subsystem"
  "stab_9_1_5"
  "stellated_dodecahedron_css"
  "subsystem_product"
  "subsystem_quantum_parity"
  "subsystem_rotated_surface"
  "surface-17"
  "symmetry_protected_self_correct"
  "tamo_barg"
  "ternary_tree_fermion"
  "twisted_xzzx"
  "two_block_quantum"
  "wasilewski-banaszek"
  "xp_stabilizer"
  "xcube"
  "xyz_color"
  "xysurface"
  "yoked_surface"
)


# Convert the list to an associative array for quick lookup
declare -A keep_map
for folder in "${keep[@]}"; do
    keep_map["$folder"]=1
done

# Get the list of all folders in the current directory
all_folders=($(find . -maxdepth 1 -type d -printf "%f\n"))

# Loop through all folders
for folder in "${all_folders[@]}"; do
    # Skip the current directory
    if [ "$folder" == "." ]; then
        continue
    fi

    # Check if the folder is not in the keep list
    if [ -z "${keep_map[$folder]}" ]; then
        echo "Deleting folder: $folder"
        rm -rf "$folder"
    else
        echo "Keeping folder: $folder"
    fi
done

