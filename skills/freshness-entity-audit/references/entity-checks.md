# Entity checks

Extract only what the site states:

- organization / brand name
- product or service titles
- people (CEO/founder patterns)
- locations ("headquartered in", "based in")
- sameAs URLs when present in JSON-LD

## Inconsistency

Flag distinct stems ("Acme Robotics" vs "Northwind Labs"), not "Acme" vs "Acme Inc".

## Ambiguity

Flag only if all of these are true:

- name is short / generic
- no industry word on the homepage
- no location entity
- no legal suffix
- no sameAs

Do not perform speculative third-party entity resolution.
