# plinta

Plinta turns Django models into interactive, permission-aware screens.

A consuming project defines plain Django models. Plinta registers them, renders them as configurable screens, enforces row- and field-level access on every read and write, and lets a non-developer rearrange those screens at runtime without a deployment.

## Status: v2 is being built

The package is being rebuilt from the bottom up, one layer at a time, against a single specification.

**[The v2 specification](design/SPEC.md)** is the only authoritative document here. It states what each layer is, what it may import, what it must not know, and what is deliberately not being built.

**[Reading the code](reading-the-code.md)** is where to start with the repository open. The specification is organised by decision, which makes it a reference and a poor introduction; that guide follows one page render through all nine layers, then one write, and says where the awkward parts are.

Beyond those two, documentation for a layer is written when that layer lands — a page describing code that does not exist is the failure mode the specification's own §21.11 catalogues.

## v1

The previous version — eighteen Django apps, ~29k LOC, all mandatory — keeps its own repository and is not part of this history.

It is a reference, not a target. Where v1 and the specification disagree, the specification is the decision and v1 is the thing being replaced — including where v1's documentation described behaviour its code never had.
