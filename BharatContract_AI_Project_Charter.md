# BharatContract AI

## Product Vision, Research Methodology, Requirements, and Execution Plan

**Document status:** Agreed project direction and proposed
implementation plan\
**Project context:** College project; constrained time and budget\
**Primary focus:** Core contract intelligence and research
methodology---not frontend/dashboard expansion\
**Repository status:** Existing implementation has been described and
partially audited through prior checks, but the current code, data,
runtime behavior, and legal claims must be independently re-verified
before implementation decisions are finalized.

------------------------------------------------------------------------

## 1. Executive Summary

BharatContract AI is intended to be a practical contract-understanding
and review system for Indian contracts. It should help businesses and
legal professionals understand what a contract says, identify potential
risks, extract obligations and deadlines, and connect possible legal
issues to trustworthy legal sources.

The product should combine dependable document processing, context-aware
clause understanding, obligation extraction, risk detection, and
evidence-grounded legal analysis. It should not pretend to replace a
lawyer, provide definitive legal verdicts, or claim broad legal coverage
that has not been demonstrated.

The project strategy is to **improve the existing implementation
incrementally**, guided by repository inspection, data availability,
error analysis, and reproducible evaluation. The project should
prioritize dependable real-world usefulness and evidence-backed claims
over novelty, breadth for its own sake, or unnecessary infrastructure.

### Core principle

Always distinguish:

1.  **What the contract says** --- supported by exact contract text.
2.  **What a legal source says** --- supported by a verified, relevant
    authority.
3.  **What the system infers** --- an interpretation that may be
    uncertain and must be labelled accordingly.

The system must be allowed to say **"insufficient evidence to
determine."**

------------------------------------------------------------------------

## 2. Product Vision and Intended Users

### 2.1 Intended users

The product is designed for both:

-   **Businesses** that need to understand agreements, obligations,
    deadlines, and commercial exposure.
-   **Legal professionals** who want a traceable first-pass review and
    structured evidence to support their work.

The system is an aid to review, not a substitute for professional legal
judgment.

### 2.2 Product objective

Deliver an evidence-first contract review that can:

-   Understand and classify contract clauses.
-   Extract obligations, responsible parties, actions, conditions, and
    deadlines.
-   Identify explicit risks and potential concerns that simple keyword
    rules may miss.
-   Identify possible missing protections without treating absence as
    proven merely because a search found no wording.
-   Explain potential Indian-law issues using trustworthy, applicable
    legal sources.
-   Show why each finding was produced and how strong the supporting
    evidence is.
-   Communicate uncertainty and coverage limits.
-   Offer optional, carefully qualified questions or negotiation
    suggestions where the evidence supports them.

### 2.3 Product priorities

In priority order:

1.  Evidence integrity and factual correctness.
2.  Reliable parsing and preservation of contract context.
3.  Useful clause and obligation understanding.
4.  Risk detection with controlled false alarms and visible serious
    concerns.
5.  Trustworthy legal grounding and applicability analysis.
6.  Explainable prioritization and useful output.
7.  Additional capabilities only when evidence shows they are
    worthwhile.

### 2.4 Explicit non-goals

The initial project should not attempt to:

-   Replace a lawyer or make definitive legal determinations.
-   Claim exhaustive coverage of Indian law or every contract type.
-   Train a large language model from scratch.
-   Buy expensive datasets or legal databases.
-   Hire annotators or require an extensive expert-labeling program.
-   Rebuild the entire application without evidence that a rewrite is
    necessary.
-   Add graphs, embeddings, LLMs, or other techniques merely for
    novelty.
-   Expand into broad multilingual support, automated redlining,
    Slack/Jira integrations, or other unrelated features unless the core
    evaluation establishes a compelling need.
-   Spend project time expanding the dashboard or frontend. The current
    priority is the core research and methodology.

------------------------------------------------------------------------

## 3. Contract Scope

### 3.1 Scope decision

Contract coverage will be chosen based on **the actual repository
implementation, usable data, and evaluation feasibility**, while
retaining moderate breadth across related contract types.

Do not select contract types based only on what sounds impressive.
Inspect the existing taxonomy, labels, data, parser behavior, risk
rules, obligation extractor, and available evaluation examples before
finalizing the supported categories.

### 3.2 Scope-selection procedure

For each candidate contract type:

1.  Determine whether the repository has relevant examples and what
    labels they actually contain.
2.  Inspect which clause categories the current classifier supports.
3.  Identify whether existing rules and models cover meaningful issues
    in that type.
4.  Check whether obligations and risk findings can be evaluated with
    available annotations or a manageable manually reviewed set.
5.  Assess practical value for businesses and legal professionals.
6.  Check whether relevant Indian legal sources can be verified and kept
    current.
7.  Estimate implementation and evaluation effort.
8.  Select a moderate, coherent set of related contract types that can
    be evaluated credibly.

Possible candidates include service agreements, master service
agreements (MSAs), consulting agreements, employment agreements, and
other categories already supported by the actual repository. These are
candidates, not commitments. The final scope must follow inspection and
evidence.

### 3.3 Coverage disclosures

The application and project report must state which contract types and
clause categories have actually been evaluated. A system that processes
a document technically must not imply that it can analyze every clause
type reliably.

------------------------------------------------------------------------

## 4. Review Perspective: Neutral by Default

### 4.1 Neutral bilateral review

The default mode reviews the agreement from both parties' perspectives.
It should:

-   Identify material obligations and risks for each party.
-   Describe imbalanced terms without automatically treating imbalance
    as illegal.
-   Distinguish legal concerns from commercial disadvantages.
-   Consider the agreement as a whole, including definitions,
    exceptions, conditions, and cross-references.
-   Explain how a clause may affect each party where the evidence
    supports that analysis.
-   Avoid assuming that the person uploading the contract represents
    either party.

### 4.2 Optional party-focused mode

A party-focused mode may be offered when the user identifies whom they
represent. It may prioritize the implications for that party, but must
not distort contract facts or legal authority.

When the represented party or contractual roles are unclear:

-   Identify parties and roles from the document where possible.
-   Ask for clarification when the role materially affects
    recommendations.
-   Continue neutral analysis when possible rather than blocking the
    entire review.
-   Distinguish the identity of a party, its contractual role, and the
    user's review perspective.

------------------------------------------------------------------------

## 5. Core Product Capabilities

The initial deliverable should focus on two core levels, with selected
advanced features only when the existing system and evaluation justify
them.

### 5.1 Level 1: Reliable contract understanding

-   Parse supported document formats.
-   Preserve clause boundaries and useful document context.
-   Classify clauses into supported categories.
-   Extract obligations and their relevant fields.
-   Identify explicit issues and potential risks.
-   Identify possible missing protections with appropriate
    qualifications.
-   Link findings to exact source text and document locations.
-   Mark unclassified or unsupported clauses rather than forcing a
    label.

### 5.2 Level 2: Evidence-grounded Indian legal analysis

Where a relevant legal source can be verified, the system should:

-   Identify the source and relevant passage.
-   Assess jurisdiction, effective date, amendments, applicability,
    exceptions, and other relevant conditions.
-   Explain how the source may relate to the contract.
-   Separate what the source establishes from the system's
    interpretation.
-   Indicate when applicability is uncertain or facts are missing.
-   Avoid legal conclusions when evidence is unavailable or conflicting.

### 5.3 Selected advanced capabilities

Potential negotiation questions, alternative wording, and party-focused
recommendations may be added selectively. They are not required to
justify a finding. Any suggestion must:

-   Be traceable to the finding and its evidence.
-   Inherit the finding's uncertainty.
-   Be labelled as a possible option, not guaranteed legally valid
    wording.
-   Avoid implying that a suggested revision is legal advice.
-   Be omitted when the evidence is too weak to support a useful
    suggestion.

------------------------------------------------------------------------

## 6. Evidence-First Output

The primary output should be an evidence-first contract review report.
This is a core product specification, not a request to expand the
frontend.

A useful report should include:

1.  **Executive summary:** key findings and major limitations.
2.  **Risk overview:** explainable High/Medium/Low prioritization, with
    reasons.
3.  **Individual findings:** issue description, exact contract passage,
    location, evidence, and reasoning.
4.  **Contract facts:** relevant clause wording and extracted details.
5.  **Obligations:** responsible party, action, object or subject where
    recoverable, conditions, deadlines, and source passage.
6.  **Legal analysis:** source authority, relevant passage,
    applicability assessment, and system interpretation kept separate.
7.  **Commercial assessment:** commercial concerns distinguished from
    potential legal issues.
8.  **Possible missing protections:** explanation of what was searched
    and why the omission may matter.
9.  **Optional next steps:** questions for counsel or possible
    negotiation points when supported.
10. **Uncertainty and coverage limits:** unresolved questions,
    unsupported clause types, missing source evidence, and cases
    requiring professional review.

Every substantive finding should be traceable to its contract evidence.
Legal findings should link to supporting legal material where available.

------------------------------------------------------------------------

## 7. Finding Categories and Uncertainty

The system must distinguish at least four outcomes.

### 7.1 Explicit issue detected

The contract contains identifiable wording that supports a specific
concern. The finding should quote or precisely locate the relevant text
and explain the concern.

### 7.2 Potential issue detected

The wording or interaction between clauses suggests a concern, but the
available evidence does not establish it conclusively. Explain what is
known, what is inferred, and what remains uncertain.

### 7.3 Possible missing protection

The system cannot find an expected safeguard after checking the
agreement's relevant wording, cross-references, definitions, exceptions,
alternative formulations, and applicable context.

Important qualifications:

-   "Not found" is not proof that the protection is absent.
-   A protection may be expressed differently or appear elsewhere.
-   Missing a protection does not automatically mean the contract is
    unlawful.
-   Distinguish a commercial recommendation from a legal requirement.
-   A legal requirement must be supported by applicable legal authority
    and facts.

### 7.4 Unclassified or requires review

Use this outcome when a clause falls outside supported categories or its
meaning cannot be established reliably. Preserve the text, explain the
limitation, and avoid forcing an incorrect classification.

### 7.5 Serious but uncertain findings

A potentially consequential issue must not disappear merely because
evidence strength or model confidence is low. Keep it visible with a
clear qualification and appropriate review warning.

Severity and evidence strength are separate dimensions. Low confidence
must not be represented as low severity.

------------------------------------------------------------------------

## 8. Risk Prioritization

### 8.1 Explainable multifactor assessment

Use an explainable assessment rather than relying solely on one model
score. Factors may include:

-   **Potential impact:** how consequential the issue could be.
-   **Evidence strength:** how directly the contract and legal sources
    support the finding.
-   **Applicability and uncertainty:** unresolved conditions,
    exceptions, jurisdiction, missing facts, or conflicting sources.
-   **Scope:** which parties, obligations, transactions, or portions of
    the agreement may be affected.
-   **Party perspective:** relevant for optional party-focused review;
    neutral review remains the default.
-   **Priority:** a High, Medium, or Low summary label with a written
    explanation.

Only use factors that can be defined and supported. Do not imply that
likelihood or legal impact can be estimated precisely when the evidence
does not permit it.

### 8.2 Risk score limitations

-   A score is a prioritization aid, not a legal verdict.
-   Model confidence is not the same as evidence strength, severity, or
    legal certainty.
-   Do not collapse serious-but-uncertain concerns into a low-priority
    result without explanation.
-   Avoid false precision in numeric scores.
-   Compare the proposed scoring approach against simpler baselines and
    retain it only if it improves practical usefulness.

------------------------------------------------------------------------

## 9. Legal Source and Grounding Policy

### 9.1 Primary-source preference

Prefer authoritative primary sources, including official legislation,
government publications, and official court materials where available.
Secondary commentary may be used as clearly distinguished supporting
context, but must not silently replace primary authority when the latter
is needed.

### 9.2 Versioned legal-source layer

For each source, preserve relevant metadata when available:

-   Source identity and issuing authority.
-   Exact relevant passage.
-   Jurisdiction.
-   Publication or retrieval information.
-   Effective date and relevant amendment/status information.
-   Verification date.
-   Relevant judgment status or precedential context, where applicable.
-   Link or identifier that allows the source to be revisited.

An offline cache may be used, but its verification date and limitations
must be visible.

### 9.3 Source-to-claim discipline

A source is not sufficient merely because it exists or mentions the same
topic. The relevant passage must actually support the particular claim
being made.

For every legal finding, assess:

1.  Is the source authentic and sufficiently authoritative?
2.  Does the cited passage support the stated proposition?
3.  Is the source applicable to the relevant jurisdiction and time?
4.  Are relevant exceptions, conditions, amendments, or missing facts
    material?
5.  Is the conclusion a direct statement of the authority or an
    interpretation by the system?
6.  Is the conclusion appropriately qualified?

### 9.4 Conflicts and missing sources

If sources conflict, applicability is unclear, or a source cannot be
verified:

-   Report the uncertainty or incomplete analysis.
-   Do not force a conclusion.
-   Do not fabricate citations, quotations, case names, sections, or
    source metadata.
-   Do not treat an unverified cached citation as current authority.
-   Preserve the unresolved issue for review.

### 9.5 Separate three layers

Legal outputs must distinguish:

**A. What the law/source says:** a faithful, source-supported account.

**B. Applicability assessment:** how the source may apply to the known
contract, jurisdiction, dates, and facts.

**C. System interpretation:** the system's analysis, with uncertainty
and limitations.

------------------------------------------------------------------------

## 10. Research Questions

The project should test, rather than assume, the following hypotheses.

1.  Does a hybrid pipeline outperform a rules-only baseline on the
    chosen held-out evaluation set?
2.  Does it outperform an ML/NLP-only baseline where a fair comparison
    is possible?
3.  Does whole-contract context improve detection or reduce false alarms
    compared with isolated-clause processing?
4.  How accurately does the system extract the responsible party,
    action, conditions, and deadlines?
5.  How often do risk findings have direct, sufficient contract
    evidence?
6.  How often do legal citations actually support the associated claim
    and apply to the scenario?
7.  Can the system identify when it should abstain or request review?
8.  Does the system retain visibility of potentially consequential
    issues without presenting uncertain findings as established facts?
9.  What errors propagate between parsing, segmentation, classification,
    extraction, risk detection, and legal grounding?
10. Which improvements yield measurable practical value relative to
    their complexity and implementation cost?

Negative or mixed results are valid research outcomes. The methodology
must not be adjusted after seeing results merely to make the system
appear successful.

------------------------------------------------------------------------

## 11. Evaluation Methodology

### 11.1 Evaluate the existing baseline first

Before changing behavior:

-   Record the exact code revision and worktree state.
-   Identify the active configuration and available model artifacts.
-   Establish which optional dependencies and models are actually
    enabled.
-   Run the current tests and relevant evaluation scripts.
-   Record results, warnings, skipped tests, environment limitations,
    and missing services.
-   Inspect actual predictions and evidence for representative
    documents.
-   Verify that reported metrics correspond to the data and artifacts
    actually used.

Do not describe a component as active simply because code for it exists.
Verify runtime behavior.

### 11.2 Compare approaches fairly

Compare, where supported by the current implementation:

1.  **Rules-only baseline:** explicit rules and deterministic patterns.
2.  **ML/NLP-only baseline:** statistical or learned components, with
    the exact active components documented.
3.  **Hybrid system:** the combined pipeline.

Use the same held-out documents, labels, and evaluation definitions
wherever possible. Clearly document unavoidable differences in inputs or
capabilities. Do not compare results from different data splits as if
they were directly comparable.

If an ML-only configuration cannot perform a task independently, report
that limitation rather than inventing a comparison.

### 11.3 Clause classification metrics

Report:

-   Per-class precision, recall, and F1.
-   Macro and weighted summaries where appropriate.
-   Confusion matrix.
-   Class support and class imbalance.
-   Unclassified/abstained examples.
-   Errors by contract type and other relevant slices.

Aggregate accuracy alone is insufficient.

### 11.4 Obligation extraction metrics

Evaluate field-level correctness for:

-   Responsible party or actor.
-   Action.
-   Object or target, where applicable.
-   Conditions and exceptions.
-   Deadline or time expression.
-   Relevant amount or other structured value when supported.
-   Source-text alignment.

Report exact-match and partial-match measures with definitions stated in
advance. Do not count a plausible-looking extracted obligation as
correct unless the source text supports it.

### 11.5 Risk detection metrics

Report:

-   Precision and recall.
-   Results by risk category.
-   False-positive and false-negative examples.
-   Missed consequential issues.
-   Duplicate or redundant findings.
-   Quality of supporting contract evidence.
-   Behavior on long, complex, unfamiliar, or cross-referenced clauses.
-   Performance for possible missing protections separately from
    explicit issues where feasible.

A high aggregate score must not conceal serious misses.

### 11.6 Legal grounding metrics

Assess separately:

-   Citation authenticity and identity.
-   Whether the cited passage supports the claim.
-   Applicability to jurisdiction, date, and relevant facts.
-   Handling of amendments, exceptions, and conflicting authorities.
-   Separation of source statements from system interpretation.
-   Unsupported or fabricated legal claims.
-   Appropriate abstention when evidence is inadequate.

Citation presence alone is not a grounding success.

### 11.7 Uncertainty and abstention

Evaluate whether uncertainty labels are meaningful and whether
abstention helps avoid unsupported conclusions. Where the sample size
supports it, measure calibration and selective performance. Document how
confidence is calculated and do not call a raw model score a calibrated
probability without validation.

Measure both sides of the trade-off:

-   Unsupported conclusions the system avoids.
-   Useful findings the system abstains from unnecessarily.

### 11.8 End-to-end evaluation

Evaluate complete contract reviews, not only isolated components. Track:

-   Errors introduced by parsing or segmentation.
-   Context lost between clauses.
-   Incorrect or incomplete extraction.
-   Unsupported risk findings.
-   Legal grounding failures.
-   Duplicated, contradictory, or confusing findings.
-   Whether the final report is traceable and useful.

Where practical, use a small, structured review rubric and qualified
reviewers for consequential legal labels.

### 11.9 Ablations

Conduct targeted ablations only when feasible and informative. Candidate
experiments include:

-   Removing the ML risk booster.
-   Comparing rule-only and hybrid clause classification.
-   Comparing isolated-clause and whole-contract context.
-   Disabling a component to measure its contribution.
-   Testing whether legal-source grounding reduces unsupported claims.

Do not run ablations merely to create a long table. Each should answer a
defined research question.

------------------------------------------------------------------------

## 12. Data and Ground Truth

### 12.1 Inspect what the existing data actually supports

Review dataset contents, annotations, source, licensing, preprocessing,
class balance, duplication, and relationship to the chosen contract
types.

Datasets such as CUAD or MAUD may be useful for specific tasks they
annotate. They must not be treated as complete ground truth for
Indian-law compliance or as proof that the system works across all
Indian contract categories.

### 12.2 Build a manageable evaluation set

If feasible within the timeline:

-   Select a manageable set of legally usable Indian contracts.
-   Use synthetic, public, licensed, or appropriately authorized
    documents.
-   Respect confidentiality, privacy, copyright, and dataset licensing.
-   Create clear annotation guidelines before labeling.
-   Obtain qualified review for consequential legal labels where
    possible.
-   Record annotator disagreement and ambiguous cases.
-   Preserve source text and evidence for every label.
-   Keep a held-out set separate from development and tuning data.

If qualified legal review is unavailable, distinguish technically
evaluated results from source-checked results and legally validated
conclusions. Do not claim expert legal validation that did not occur.

### 12.3 Leakage prevention

-   Identify exact and near-duplicate documents.
-   Watch for template variants that could leak across train and test
    splits.
-   Split by contract or template family when appropriate.
-   Keep the held-out evaluation set out of rule tuning and threshold
    selection.
-   Document the split procedure and random seeds where applicable.
-   Do not repeatedly tune against the final test set.

### 12.4 Dataset limitations

For each reported metric, state which documents and labels support it,
the size of the evaluation set, important exclusions, and any limits on
generalization.

------------------------------------------------------------------------

## 13. Proposed Technical Pipeline

This is a target architecture to verify and refine, not a claim that
every stage already works correctly.

1.  **Document ingestion:** identify file type, extract text, preserve
    source locations, and report extraction failures.
2.  **Segmentation:** identify clauses and subclauses while preserving
    headings and relevant context.
3.  **Contract structure:** identify parties, definitions,
    cross-references, conditions, and related clauses where feasible.
4.  **Clause classification:** assign supported labels or abstain.
5.  **Entity and value extraction:** identify supported dates, amounts,
    identifiers, jurisdictions, and other relevant entities.
6.  **Obligation extraction:** identify actors, actions, conditions, and
    deadlines with source-text alignment.
7.  **Risk detection:** combine explicit rules and learned patterns
    where justified.
8.  **Whole-contract contextual review:** connect relevant clauses,
    exceptions, definitions, and cross-references.
9.  **Legal-source grounding:** retrieve and verify relevant authority
    when available.
10. **Finding assessment:** separate severity, evidence strength,
    applicability, and uncertainty.
11. **Deduplication and consistency:** detect duplicate, contradictory,
    or overlapping findings.
12. **Evidence-first report:** present supported findings, uncertainty,
    priorities, and review limitations.

Each stage should expose enough information to investigate errors. Avoid
silent fallback behavior that makes a failed stage look successful.

------------------------------------------------------------------------

## 14. Existing Repository: Reported Context to Verify

The following is prior repository context and must be independently
re-checked against the actual current checkout before it drives code
changes or factual project claims.

### 14.1 Reported stack and layout

-   Python 3.10--3.12, `uv`, FastAPI, Streamlit, Neo4j, PostgreSQL, and
    optional Redis.
-   scikit-learn and optional PyTorch/Transformers components.
-   Document parsing using libraries such as `pdfplumber`, PyMuPDF,
    `python-docx`, and optional OCR.
-   `app/main.py`, `app/core`, `app/api`, `app/db`, `app/models`,
    `app/services`, and `app/utils`.
-   `nlp/` components reportedly include taxonomy and dataset label
    mappings, clause classification, entity extraction, obligation
    extraction, risk rules/scoring, case-law pointers, and an ML risk
    booster.
-   Scripts, tests, sample contracts, CUAD/MAUD-related data, and
    processed model artifacts have been reported.
-   A Streamlit UI/dashboard exists, but expanding it is not a project
    priority.

### 14.2 Reported pipeline

The reported pipeline is:

**parse → segment → classify → entity extraction → obligation extraction
→ risk rules → ML risk booster → score/report**

Actual call paths, error handling, runtime activation, and data flow
must be verified.

### 14.3 Reported parser behavior

Prior context describes PDF extraction using `pdfplumber`, then PyMuPDF,
with OCR attempted under a reported low-text threshold; DOCX, TXT, and
Markdown support; a reported character cap; and header/footer cleanup.

These details are unverified implementation notes. Test them against
representative files, especially scanned PDFs, long contracts, tables,
and documents with unusual layouts.

### 14.4 Reported classification and risk behavior

Prior context describes a classifier combining rules and TF-IDF,
optional DeBERTa, regex-first entity extraction, modal-pattern
obligation extraction, a set of risk rules, contract-level
missing-clause checks, an ML risk booster, and a weighted risk score.

Do not assume these methods are correct or active. Establish which model
artifacts are present, which optional dependencies are installed, and
which components actually execute in the target environment.

### 14.5 Reported verification snapshot

Prior checks reportedly found:

-   Git `main` at `cbd9c29`, with an untracked `.commandcode/`
    directory.
-   `uv lock --check` succeeded.
-   Ruff passed.
-   Pytest showed 38 test dots and exit code 0, although the final
    summary line was not captured.
-   Importing `app.main` succeeded.
-   Optional PyTorch/Transformers dependencies were absent in the
    checked environment, so some transformer-based functionality was
    inactive.
-   PostgreSQL and Neo4j services were not running, so persistence
    behavior was not fully exercised.
-   `data/processed/` was reportedly untracked or absent from Git
    tracking; some classifier tests may therefore behave differently on
    a clean clone.
-   `requirements.txt` and `pyproject.toml` reportedly differed.
-   A potential compatibility issue involving `passlib` and `bcrypt` was
    noted for verification.
-   Tests reportedly create ignored runtime files.

These are historical reports, not proof of the current repository state.
Re-run the relevant checks in the actual working environment before
relying on them. Do not claim database durability, authorization
behavior, transformer performance, or legal accuracy based on these
checks alone.

------------------------------------------------------------------------

## 15. Integrity, Reproducibility, and Change Control

The project should use a zero-trust approach to research outputs.

### 15.1 Before trusting any run

Verify:

-   **Identity:** correct repository, branch, commit, and experiment.
-   **State:** actual configuration, environment, dependencies, and
    active components.
-   **Output:** expected files exist and are readable.
-   **Provenance:** outputs correspond to the stated code, config, data,
    and run.
-   **Completeness:** expected documents, predictions, and metrics are
    present.
-   **Validity:** outputs pass structural and semantic checks; metrics
    were computed correctly.

A successful process exit alone is not sufficient evidence that a run is
valid.

### 15.2 Record experiment provenance

For each meaningful run, record as applicable:

-   Repository commit and worktree state.
-   Configuration and relevant parameter values.
-   Dataset identity, version, and split.
-   Model artifact identity or hash.
-   Environment and dependency versions.
-   Random seeds and deterministic settings where relevant.
-   Start/end status and exit code.
-   Input and output counts.
-   Warnings, skipped items, and failures.
-   Metric-generation procedure.
-   Output paths and artifact hashes where practical.

### 15.3 Reproducibility

-   Keep evaluation scripts deterministic where possible.
-   Record non-deterministic components and known sources of variation.
-   Preserve raw predictions and intermediate evidence needed to
    investigate errors.
-   Never silently replace results or hide failed runs.
-   Keep a decision log for methodological changes.
-   Do not make a claim stronger than the evidence supports.

### 15.4 Safe repository work

-   Inspect the current repository and its agent/developer instructions
    before editing.
-   Establish the baseline before changing code.
-   Prefer small, reviewable changes with tests.
-   Avoid destructive Git history operations unless explicitly approved.
-   Do not discard user changes, stashes, untracked handoff documents,
    or experiment artifacts.
-   Do not synchronize scripts or alter active experiments unless a
    run/campaign is active and there is a clear need.
-   Avoid unsupported fixes and speculative refactors.

------------------------------------------------------------------------

## 16. Development Roadmap

The exact calendar depends on the project deadline, which has not yet
been specified. The phases below are ordered by dependency and can be
compressed or prioritized based on available time.

### Phase 1 --- Establish repository and research baseline

**Goal:** determine what exists and what works.

Tasks:

-   Inspect repository instructions, current branch, commit, worktree,
    and untracked files.
-   Map the actual execution path and identify active components.
-   Inspect datasets, labels, artifacts, licensing, and evaluation
    scripts.
-   Run tests and record complete output.
-   Verify parser, classifier, extraction, risk, and legal-source
    behavior with representative examples.
-   Record runtime and infrastructure limitations.
-   Create a baseline results table and list unresolved questions.

**Exit condition:** the baseline is reproducible enough to describe, and
major unknowns are documented.

### Phase 2 --- Audit errors and choose priorities

**Goal:** focus effort on demonstrated weaknesses.

Inspect examples of:

-   Lost context or broken clause segmentation.
-   Incorrect or incomplete obligations.
-   Risk findings without adequate evidence.
-   Serious issues missed by the current system.
-   Unsupported or inapplicable legal citations.
-   Duplicate or contradictory findings.
-   Long and unfamiliar contracts.
-   Incorrect certainty or risk prioritization.

Rank fixes by expected practical impact, evidence strength,
implementation cost, and evaluation feasibility.

**Exit condition:** a short, justified list of high-impact changes with
tests that can show whether each change helps.

### Phase 3 --- Implement targeted improvements

**Goal:** improve the existing system without unnecessary rewrites.

Possible priorities, chosen only after Phase 2:

-   Preserve clause context and source locations.
-   Improve obligation field extraction and evidence alignment.
-   Reduce unsupported risk findings.
-   Improve legal citation verification and applicability metadata.
-   Make abstention and uncertainty behavior explicit.
-   Improve duplicate detection and whole-contract consistency.
-   Fix reproducibility or clean-clone issues that block valid
    evaluation.

Every change should include regression tests and a clear rationale. Add
new models or infrastructure only if a measured need justifies them.

**Exit condition:** targeted tests pass and the improvement can be
evaluated against the baseline.

### Phase 4 --- Evaluate improvements

**Goal:** establish whether changes genuinely help.

-   Run the same held-out evaluation as the baseline.
-   Compare rules-only, ML/NLP-only, and hybrid methods where feasible.
-   Report per-class metrics and important errors.
-   Check serious misses and false alarms.
-   Evaluate evidence support and legal grounding separately.
-   Run targeted ablations when useful.
-   Record regressions and negative results.
-   Preserve exact provenance for all reported metrics.

**Exit condition:** the final claims are supported by reproducible
results and explicit limitations.

### Phase 5 --- Document and demonstrate

**Goal:** deliver a defensible college research project.

Deliver:

-   Product and system design.
-   Reproducible evaluation methodology.
-   Baseline and final results.
-   Representative success and failure cases.
-   Legal-source and uncertainty policy.
-   Limitations and future work.
-   Setup and evaluation instructions.
-   A concise demonstration based on verified examples.

Do not claim legal validation unless qualified validation actually
occurred.

------------------------------------------------------------------------

## 17. Acceptance Criteria

Define exact numeric thresholds before the final evaluation once the
baseline and evaluation-set size are known. Do not invent thresholds in
advance without understanding the baseline, class balance, or practical
error costs.

At minimum, the project should meet these qualitative criteria:

### Correctness and traceability

-   Findings can be traced to exact contract text.
-   Extracted obligations are supported by their source passages.
-   Legal citations are authentic and their supporting passages are
    checked.
-   Source statements, applicability analysis, and system interpretation
    are distinct.
-   Unsupported conclusions are not presented as facts.

### Coverage and uncertainty

-   Supported contract types and categories are explicitly documented.
-   Unfamiliar clauses can be left unclassified or sent for review.
-   Potentially consequential but uncertain concerns remain visible with
    qualifications.
-   Possible missing protections are not automatically labelled illegal.
-   Neutral bilateral review does not assume the uploader's role.

### Evaluation

-   A baseline is recorded.
-   Evaluation data is held out from tuning.
-   Class-level and task-appropriate metrics are reported.
-   Serious misses, false positives, and legal-grounding failures are
    examined.
-   The final evaluation is reproducible from recorded code, data,
    configuration, and artifacts.
-   Claims are limited to the demonstrated evidence.

### Engineering

-   Existing tests pass, or failures are documented and understood.
-   New behavior has regression tests.
-   Clean-clone and missing-artifact behavior are checked.
-   External service limitations are disclosed.
-   No unnecessary rewrite or infrastructure dependency is introduced.

------------------------------------------------------------------------

## 18. Risks and Mitigations

  -----------------------------------------------------------------------
  Risk                                Mitigation
  ----------------------------------- -----------------------------------
  False legal claims                  Verify source identity, relevant
                                      passage, applicability, and
                                      uncertainty; abstain when evidence
                                      is insufficient.

  False alarms                        Evaluate precision and false
                                      positives; require evidence and
                                      inspect errors.

  Serious missed issues               Track consequential false negatives
                                      separately and keep uncertain
                                      serious concerns visible.

  Missing-protection errors           Check the whole contract and
                                      distinguish absence of a detected
                                      phrase from actual absence.

  Dataset mismatch                    Use each dataset only for labels
                                      and tasks it genuinely supports.

  Data leakage                        Detect near-duplicate documents and
                                      separate template families where
                                      appropriate.

  Overfitting to the test set         Keep a held-out set untouched
                                      during tuning and define criteria
                                      in advance.

  Inactive optional models            Verify runtime activation and
                                      artifacts; report the actual tested
                                      configuration.

  Unavailable databases/services      Test and document degraded behavior
                                      separately from full persistence
                                      behavior.

  Over-engineering                    Add techniques only when a
                                      demonstrated problem and measurable
                                      evaluation justify them.

  Time constraints                    Prioritize core reliability and
                                      evaluation over broad feature
                                      expansion.

  Overstated project claims           Separate software testing,
                                      empirical performance, source
                                      verification, and qualified legal
                                      validation.
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 19. Reporting Standards

Every project report, README claim, presentation, and demonstration
should distinguish:

-   Implemented versus planned functionality.
-   Available versus actually activated models.
-   Unit-test success versus end-to-end correctness.
-   Technical performance versus legal validation.
-   Source retrieval versus source verification.
-   A detected issue versus a potential issue.
-   Missing text detected versus a legally required protection confirmed
    absent.
-   Model confidence versus evidence strength and severity.
-   Demonstrated coverage versus intended future coverage.

When a result is unknown, report it as unknown. When a check could not
run, explain why. Do not convert a blocked check into a pass.

------------------------------------------------------------------------

## 20. Decisions Already Agreed

The following decisions represent the agreed direction of the project:

1.  **Product first:** prioritize dependable real-world usefulness and
    rigorous evidence.
2.  **College-project constraints:** use free and existing resources
    where possible; avoid expensive data, extensive annotation programs,
    and unnecessary complexity.
3.  **Existing code first:** inspect and improve the current
    implementation rather than rebuilding it by default.
4.  **Moderate contract breadth:** choose related contract types based
    on actual code, usable data, and evaluation feasibility.
5.  **Core capabilities:** reliable contract understanding plus
    evidence-grounded Indian legal analysis.
6.  **Neutral by default:** review both parties; offer party-focused
    analysis only when the represented party is clear.
7.  **Evidence-first findings:** cite exact contract text and relevant
    legal passages.
8.  **Separate facts and interpretation:** distinguish contract wording,
    legal authority, applicability assessment, and system inference.
9.  **Explicit uncertainty:** permit abstention and preserve serious but
    uncertain concerns for review.
10. **Distinct finding categories:** explicit issue, potential issue,
    possible missing protection, and unclassified/requires review.
11. **Explainable prioritization:** assess potential impact, evidence
    strength, applicability, uncertainty, and scope; use High/Medium/Low
    labels only as a summary.
12. **Legal source integrity:** prefer verified primary sources, track
    relevant source metadata, and never fabricate authority.
13. **Research comparisons:** compare rules-only, ML/NLP-only, and
    hybrid approaches where fair and feasible.
14. **Task-specific evaluation:** assess classification, obligations,
    risks, legal grounding, uncertainty, and end-to-end behavior.
15. **Reproducibility:** verify identity, state, output, provenance,
    completeness, and validity before trusting a run.
16. **Incremental roadmap:** establish baseline, audit errors, implement
    targeted fixes, evaluate, and document.
17. **No frontend expansion priority:** concentrate on core research,
    methods, code correctness, and evaluation.
18. **Honest reporting:** preserve negative results and disclose
    limitations.

------------------------------------------------------------------------

## 21. Open Items for Repository Inspection

These are deliberately not assumed to be settled:

-   Which contract types have the strongest real support in the current
    implementation?
-   Which dataset annotations can legitimately support each evaluation
    task?
-   Which model components and artifacts are active in the intended
    runtime?
-   Are baseline metrics reproducible?
-   What are the highest-impact observed errors?
-   Which legal-source references are authentic, current, and
    applicable?
-   Can the current pipeline preserve source locations and cross-clause
    context?
-   Which persistence and authorization behaviors can be verified with
    available services?
-   What clean-clone failures occur because of untracked artifacts or
    optional dependencies?
-   Which exact numeric acceptance thresholds are justified by the
    baseline and evaluation set?
-   What is the actual project deadline, and which roadmap phases fit
    it?

Resolve these questions through inspection and measurement, not guesses.

------------------------------------------------------------------------

## 22. Immediate Next Actions

When work begins, proceed in this order:

1.  Inspect the actual checkout, repository instructions, Git state, and
    untracked files.
2.  Map the real pipeline and runtime configuration.
3.  Inspect datasets, labels, licensing, artifacts, and current
    evaluation code.
4.  Run and record the baseline checks.
5.  Examine representative outputs and failure cases.
6.  Select contract scope and measurable research questions based on
    findings.
7.  Define the evaluation set, split rules, annotation guidance, and
    acceptance criteria before tuning.
8.  Implement only the highest-impact justified improvements.
9.  Evaluate with the same held-out data and record all results.
10. Produce the final report with reproducibility details, limitations,
    and evidence-backed claims.

**Do not start by adding features. Start by establishing what the
existing system actually does and what the evidence shows it needs.**

------------------------------------------------------------------------

## Final Project Principle

BharatContract AI should be judged not by how many risks it reports or
how sophisticated its architecture sounds, but by whether its findings
are useful, traceable, appropriately qualified, and supported by
reproducible evidence.

**Trustworthiness is a functional requirement, not a marketing claim.**
