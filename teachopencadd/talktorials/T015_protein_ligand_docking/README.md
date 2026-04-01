# T015 · Protein ligand docking

**Note:** This talktorial is a part of TeachOpenCADD, a platform that
aims to teach domain-specific skills and to provide pipeline templates
as starting points for research projects.

Authors:

- Jaime Rodríguez-Guerra, 2019-20, [Volkamer lab,
  Charité](https://volkamerlab.org/)
- Dominique Sydow, 2019-20, [Volkamer lab,
  Charité](https://volkamerlab.org/)
- Michele Wichmann, 2019-20, student work at [Volkamer lab,
  Charité](https://volkamerlab.org/)
- Maria Trofimova, CADD seminar, 2020, Charité/FU Berlin
- David Schaller, 2020-21, [Volkamer lab,
  Charité](https://volkamerlab.org/)
- Andrea Volkamer, 2021, [Volkamer lab,
  Charité](https://volkamerlab.org/)

## Aim of this talktorial

In this talktorial, we will use molecular docking to predict the binding
mode of a small molecule in a protein binding site. The epidermal growth
factor receptor ([EGFR](https://www.uniprot.org/uniprot/P00533)) will
serve as a model system to explain important steps of a molecular
docking workflow with the docking software
[Smina](https://sourceforge.net/projects/smina/), a fork of Autodock
Vina.

### Contents in *Theory*

- Molecular docking
- Sampling algorithms
- Scoring functions
- Limitations
- Visual inspection
- Docking software
  - Commercial
  - Free (for academics)

### Contents in *Practical*

- Preparation of protein and ligand
- Binding site definition
- Docking calculation
- Docking results visualization

### References

- Molecular docking:
  - Pagadala *et al.*, [*Biophy Rev* (2017), **9**,
    91-102](https://doi.org/10.1007/s12551-016-0247-1)
  - Meng *et al.*, [*Curr Comput Aided Drug Des* (2011), **7**, 2,
    146-157](https://doi.org/10.2174/157340911795677602)
  - Gromski *et al.*, [*Nat Rev Chem* (2019), **3**,
    119-128](https://doi.org/10.1038/s41570-018-0066-y)
- Docking and scoring function assessment:
  - Warren *et al.*, [*J Med Chem* (2006), **49**, 20,
    5912-31](https://doi.org/10.1021/jm050362n)
  - Wang *et al.*, [*Phys Chem Chem Phys* (2016), **18**, 18,
    12964-75](https://doi.org/10.1039/c6cp01555g)
  - Koes *et al.*, [*J Chem Inf Model* (2013), **53**, 8,
    1893-1904](https://doi.org/10.1021/ci300604z)
  - Kimber *et al.*, [*Int J Mol Sci*, (2021), **22**, 9,
    1-34](https://doi.org/10.3390/ijms22094435)
  - McNutt *et al.*, [*J Cheminform* (2021), **13**, 43,
    13-43](https://doi.org/10.1186/s13321-021-00522-2)
- Visual inspection of docking results: Fischer et al., [*J Med Chem*
  (2021), **64**, 5,
  2489–2500](https://doi.org/10.1021/acs.jmedchem.0c02227)
- Tools used
  - [OpenBabel](http://openbabel.org)
  - [Smina](https://sourceforge.net/projects/smina/)
  - [NGLView](http://nglviewer.org/nglview/latest/)
