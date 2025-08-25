variants_prompt = """
You are an expert in scientific literature analysis. Your task is to extract all **gene–variant pairs** that have been **functionally tested** in the given research article.

Only include variants that were explicitly evaluated in **functional assays** (e.g., reporter assays, CRISPR knockouts, RNA sequencing, electrophysiology, MPRA, etc.). Ignore variants that are only predicted or mentioned but not experimentally tested.

Extract only variants starting with p., c., or r.

When the same variant appears in multiple nomenclatures (g., c., p.), keep only the **lowest-level notation** according to the hierarchy: g > c > p.
- Example: if a variant appears as both "g.123A>T" and "c.456A>T", keep "c.456A>T".
- If a variant appears as "g.123A>T", "c.456A>T", and "p.Lys152Arg", keep only "p.Lys152Arg".
- If a variant contains multiple notations together (e.g., "c.190_210del (p.Pro64_Pro70del)"), keep only "p.Pro64_Pro70del".

Remove duplicates so each gene–variant pair appears only once.

### Your output must be a JSON object with a `"data"` key containing an array of objects. Each object must include:

- `"gene"`: The gene symbol (e.g., "MYBPC3")
- `"variant"`: The variant designation (e.g., "c.1224-52G>A", "p.G148R")

### Example:

Input sentence:
"The variant g.12345A>G, also reported as c.456A>G and resulting in p.Lys152Arg, was functionally tested in HEK293 cells."

Output:
```json
{
  "data": [
    {
      "gene": "GENE1",
      "variant": "p.Lys152Arg"
    }
  ]
}
"""