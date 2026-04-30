#!/usr/bin/env python3
"""Fetch the parity check matrix of the Steane [[7,1,3]] code from qecdb.org.

The H field encodes stabilizer generators as Pauli strings, e.g.:
  'XXXIXII XXIXIIX ...'
Each space-separated token is one stabilizer row.
"""

import pymongo
import numpy as np

client = pymongo.MongoClient("mongodb://qumbauser:tetracode@qecdb.org")
db = client["qumba"]
codes = db["codes"]

# The Steane code is the unique [[7,1,3]] self-dual CSS code
query = {"n": 7, "k": 1, "d": 3}
cursor = codes.find(query)

results = list(cursor)
print(f"Found {len(results)} [[7,1,3]] code(s) in qecdb.\n")

for data in results:
    print(f"ID:       {data['_id']}")
    print(f"Name:     {data.get('name', 'N/A')}")
    print(f"CSS:      {data.get('css')}, self-dual: {data.get('selfdual')}")
    print(f"Automorphisms: {data.get('automorphisms')}")

    h_str = data.get("H", "")
    if not h_str:
        print("No H field found.")
        continue

    rows = h_str.split()
    print(f"\nStabilizer generators (H field, {len(rows)} rows x {len(rows[0])} qubits):")
    for row in rows:
        print(" ", row)

    # Convert Pauli strings to binary symplectic form [X-part | Z-part]
    n = len(rows[0])
    X = np.zeros((len(rows), n), dtype=int)
    Z = np.zeros((len(rows), n), dtype=int)
    for i, row in enumerate(rows):
        for j, p in enumerate(row):
            if p in ("X", "Y"):
                X[i, j] = 1
            if p in ("Z", "Y"):
                Z[i, j] = 1

    H_symplectic = np.hstack([X, Z])
    print(f"\nBinary symplectic parity check matrix H = [X | Z]  ({H_symplectic.shape}):")
    print(H_symplectic)
    print()
