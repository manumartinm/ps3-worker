first_extraction_prompt = """
You are an expert scientific literature analyst. Your task is to extract detailed experimental information for a the following gene: {gene} and this variant: {variant}.

You will be provided with a gene and a variant. Your task is to confirm whether this pair was tested in a functional assay in the article, and if so, extract all related data.

The output must be a **valid JSON object** (not a list) with a key `"data"` containing a single object structured according to the `ResearchArticle` schema. Each field must be a JSON object with the following structure:

- `"value"`: the extracted value.
- `"explanation"`: a detailed explanation describing:
  - Why this value was chosen.
  - Where exactly it was found in the paper (text fragment or section).
  - How it was derived (if inference or summarization was involved).

### Required fields in the response:
1. **articulo**: Full article title.
2. **doi**: DOI as a hyperlink (e.g., `https://doi.org/...`).
3. **disease**: Full name of the disease without abbreviations.
4. **gene**: The specific gene provided.
5. **variant_name**: The specific variant provided.
6. **type**: Type of experiment performed, using ontology terms (e.g., `OBI:0000854`). Include both the name and identifier.
7. **modelSystem**: Experimental system used (`in vitro`, `in vivo`, `ex vivo`, or `in silico`).
8. **experimentalMethod**: Summary of the experimental method or assay.
9. **outcomeEvaluated**: Key functional or biological outcome being measured.
10. **positiveControls**: Number and description of positive control samples used.
11. **negativeControls**: Number and description of negative control samples used.
12. **pathogenicVariants**: Total number of pathogenic variants analyzed in the experiment.
13. **pathogenicAbnormalVariants**: Number of pathogenic variants with functionally abnormal (or normal) results.
14. **totalVariants**: Total number of variants analyzed.
15. **replicates**: Number of biological or technical replicates used.
16. **statisticalAnalysis**: Description of statistical tests or software used.
17. **validationProcess**: Steps or criteria used to validate the findings.
18. **reproducible**: Boolean (`true`/`false`) indicating reproducibility based on the article.
19. **robustnessData**: Details about sample origin, treatment, transport, and storage.
20. **functionalImpact**: Final interpretation of the variant (e.g., `functionally abnormal`, `normal`, or `unknown`) and the molecular mechanism if available.

### Reasoning process:
1. Confirm that the given gene–variant pair appears in the paper and was tested functionally.
2. Extract all relevant data related to this specific experiment.
3. Structure your response with clear traceability for each field using the `value` + `explanation` format.
4. If the variant was not tested functionally, respond with a JSON object where each `"value"` is `null` and the `"explanation"` indicates that the variant was not tested.

Be precise, transparent, and only report what is supported by the article.
"""
