refine_results_prompt = """
You are an expert in extracting structured scientific information from text.

Your task is to **review and refine** the extracted information for genes tested in a scientific paper.

You will receive:
- A list of gene-level data objects under `extracted_data`. Each object contains only a subset of fields (e.g., one or more) to be reviewed and possibly updated.
- A section of source text under `rag_results_text` from which the extracted data was derived.

⚠️ Your goal is to:
- **Only review and update the fields that are explicitly included in each entry of `extracted_data`.**
- **Leave all other fields untouched and unmodified.**

For each field present:
- Carefully read the `rag_results_text` and **check if the current value is accurate** based only on the evidence in the text.
- If the value is correct, keep it and set the `"explanation"` to something like `"Verified from text, no change needed."`
- If the value is incorrect or incomplete, **correct it** using only the information in `rag_results_text` and provide a concise explanation of what was changed and why.

Do NOT use external knowledge or assumptions.

---

## Already Extracted Data:

{extracted_data}

## Provided Text Excerpts:

{rag_results_text}

---

## Instructions Recap:

- Operate only on the fields present in `extracted_data`.
- Preserve existing values if they are supported by the text and clearly explain why no change is needed.
- If the text contradicts or provides a more accurate value, update the `value` and clearly explain the correction in `explanation`.
- Each field in each object must follow this structure:
```json
"field_name": {
  "value": <corrected or confirmed value>,
  "explanation": "<your reasoning based strictly on the text>"
}
"""
