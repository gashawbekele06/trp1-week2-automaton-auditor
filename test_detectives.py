# test_detectives.py
from src.graph import app

# ← Replace with REAL values
TEST_REPO = "https://github.com/gashawbekele06/trp1-week2-automaton-auditor"
TEST_PDF  = "reports/Week2-Interim_report" \
".pdf"   # put a PDF file here or adjust path

result = app.invoke({
    "repo_url": TEST_REPO,
    "pdf_path": TEST_PDF,
})

print("Final evidences collected:")
print(result.get("evidences", "No evidences collected"))

print("\nCurrent dimension index:", result.get("current_dimension_index"))
print("Repo path (temp):", result.get("repo_path"))