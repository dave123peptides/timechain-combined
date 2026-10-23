"""Research-framed product copy for the lyophilized vial line, ported
from the vial site's app.scripts.sync_product_content on 2026-10-22
(David's 2026-08-24 direction there: competitor-depth PDP copy with no
purity numbers, no competitor comparisons, no study citations and no
human dosing guidance).

Consumed by app.scripts.seed_lyo_catalog. For a compound that also ships
as a pen, seed_pen_catalog owns the product's name, tagline and overview
(David's TCP Guide wording); this copy only fills the structured keys
the pen seed leaves empty (key_points, research_areas, pairs_with, faq).
For a vial-only compound the whole entry applies.

slug -> (description, content). description is a single-sentence tagline;
content.overview is the longer "What is this?" paragraph. research_areas
is framed as "studied for X in Y context", never as a claim about what the
compound does in a human body.
"""

LYO_CONTENT: dict[str, tuple[str, dict]] = {
    # TODO(attorney-review): GLP-class copy — Janesa to review before public
    # launch. Mechanism language is deliberately confined to the research
    # sections and framed as what is studied, never as a product claim. No
    # drug-name mapping, no human outcome (weight, appetite, body
    # composition). See docs/plans for the FDA warning-letter context.
    "glp-1s": (
        "A metabolic-pathway research compound. Receptor activity and published "
        "literature are described in the research sections of this page.",
        {
            "overview": (
                "GLP-1S is studied as a single-receptor incretin compound. Research in this area "
                "investigates glucose-dependent insulin secretion and related incretin receptor "
                "signalling in preclinical models. It is among the most frequently referenced "
                "compound classes in the metabolic literature of the past decade."
            ),
            "key_points": [
                "Single-receptor incretin compound",
                "Investigated in glucose-regulation pathway research",
                "Widely referenced in the metabolic literature",
            ],
            "research_areas": [
                "Glucose-dependent insulin secretion pathways",
                "Incretin receptor signalling in preclinical models",
                "Comparative studies alongside GLP-2T and GLP-3R",
            ],
            "pairs_with": ["cagrilinitide", "bac-water"],
        },
    ),
    # TODO(attorney-review): see the note on glp-1s.
    "glp-2t": (
        "A metabolic-pathway research compound. Receptor activity and published "
        "literature are described in the research sections of this page.",
        {
            "overview": (
                "GLP-2T is studied as a dual-receptor incretin compound, engaging the GIP and GLP-1 "
                "receptors. Published work in this area investigates whether engaging two incretin "
                "receptors produces a different signalling profile in preclinical models than "
                "engaging one."
            ),
            "key_points": [
                "Dual-receptor incretin compound (GIP, GLP-1)",
                "Common reference point in comparative incretin studies",
                "Available across four research-relevant dose tiers",
            ],
            "research_areas": [
                "Combined incretin receptor signalling",
                "Comparative pathway studies against single-receptor compounds",
                "Insulin sensitivity research models",
            ],
            "pairs_with": ["cagrilinitide", "bac-water"],
        },
    ),
    # TODO(attorney-review): see the note on glp-1s.
    "glp-3r": (
        "A metabolic-pathway research compound. Receptor activity and published "
        "literature are described in the research sections of this page.",
        {
            "overview": (
                "GLP-3R is studied as a multi-receptor compound engaging the GIP, GLP-1 and glucagon "
                "receptors. Research in this area investigates how multi-receptor engagement alters "
                "metabolic signalling in preclinical models relative to single- and dual-receptor "
                "compounds."
            ),
            "key_points": [
                "Multi-receptor compound (GIP, GLP-1, glucagon)",
                "Broadest receptor coverage in this catalog",
                "Available across five research-relevant dose tiers",
            ],
            "research_areas": [
                "Multi-receptor incretin and glucagon signalling",
                "Metabolic regulation in preclinical models",
                "Comparative studies against single- and dual-receptor compounds",
            ],
            "pairs_with": ["cagrilinitide", "bac-water"],
        },
    ),
    # NOTE(attorney-review): research_areas includes "Body composition
    # research models". Research-framed rather than a product claim, so left
    # as authored — flagged for review alongside the GLP-class copy.
    "tesamorelin": (
        "A GHRH analog studied for its role in growth hormone pulsatility research.",
        {
            "overview": (
                "Tesamorelin is a synthetic analog of growth hormone-releasing hormone (GHRH). It binds "
                "the GHRH receptor on the pituitary, stimulating the body's own pulsatile GH release "
                "rather than introducing exogenous GH directly — a mechanism researchers use to study "
                "the upstream regulation of the GH axis."
            ),
            "key_points": [
                "GHRH receptor agonist",
                "Stimulates endogenous, pulsatile GH release",
                "Well-characterized in GH-axis literature",
            ],
            "research_areas": [
                "Pituitary GHRH receptor signaling",
                "Pulsatile growth hormone secretion patterns",
                "Body composition research models",
            ],
            "faq": [
                {
                    "q": "How is this different from Sermorelin?",
                    "a": "Both are GHRH analogs. Tesamorelin is a modified, longer sequence; Sermorelin "
                    "is the shorter GHRH(1-29) fragment. Researchers often compare the two for "
                    "differences in receptor binding duration.",
                }
            ],
            "pairs_with": ["ipamorelin", "tesamorelin-ipamorelin", "bac-water"],
        },
    ),
    "sermorelin": (
        "A GHRH(1-29) fragment used in growth hormone axis research.",
        {
            "overview": (
                "Sermorelin corresponds to the first 29 amino acids of endogenous GHRH — the shortest "
                "fragment still shown to retain full GHRH receptor activity. It's a foundational compound "
                "in growth hormone secretagogue research."
            ),
            "key_points": [
                "GHRH(1-29) — the minimal active GHRH fragment",
                "Foundational reference compound in GH secretagogue studies",
                "Frequently stacked with GHRP-class compounds in research protocols",
            ],
            "research_areas": [
                "GHRH receptor structure-activity relationships",
                "Pulsatile GH release mechanisms",
                "Comparative studies against longer-acting GHRH analogs",
            ],
            "pairs_with": ["ipamorelin", "bac-water"],
        },
    ),
    # NOTE(attorney-review): the overview mentions appetite only to describe
    # what this compound does NOT do (receptor selectivity vs. older GHRP
    # compounds). Left as authored; flagged for review.
    "ipamorelin": (
        "A selective ghrelin-receptor (GH secretagogue) agonist studied for its GH-release specificity.",
        {
            "overview": (
                "Ipamorelin is a pentapeptide ghrelin-receptor agonist studied for its selectivity — "
                "in research literature it's frequently noted for stimulating GH release with minimal "
                "effect on cortisol, prolactin, or appetite compared to older GHRP-class compounds."
            ),
            "key_points": [
                "Selective ghrelin receptor (GHS-R) agonist",
                "Frequently referenced for receptor selectivity vs. GHRP-2/GHRP-6",
                "Common stacking partner for GHRH analogs",
            ],
            "research_areas": [
                "Ghrelin receptor selectivity studies",
                "Comparative GH secretagogue research (vs. GHRP-2, GHRP-6)",
                "Synergy studies when paired with GHRH analogs",
            ],
            "pairs_with": ["tesamorelin", "sermorelin", "cjc-no-dac-ipamorelin", "bac-water"],
        },
    ),
    "tesamorelin-ipamorelin": (
        "A pre-blended GHRH + ghrelin-receptor agonist stack for dual-pathway GH research.",
        {
            "overview": (
                "This blend combines Tesamorelin (a GHRH receptor agonist) with Ipamorelin (a selective "
                "ghrelin receptor agonist) in one vial. Researchers use dual-pathway stacks like this to "
                "study whether engaging both GH-release mechanisms simultaneously produces a different "
                "secretion pattern than either compound alone."
            ),
            "key_points": [
                "Combines two distinct GH-release mechanisms in one vial",
                "GHRH receptor + ghrelin receptor dual agonism",
                "Pre-blended — no separate reconstitution/mixing needed",
            ],
            "research_areas": [
                "Dual-pathway GH secretagogue synergy",
                "Comparative studies vs. single-compound protocols",
            ],
            "faq": [
                {
                    "q": "Why stack Tesamorelin with Ipamorelin instead of using one alone?",
                    "a": "The two compounds act on different receptors (GHRH receptor vs. ghrelin "
                    "receptor). Research interest in stacking them centers on whether dual-pathway "
                    "stimulation changes the GH release pattern compared to single-pathway agonism.",
                }
            ],
            "pairs_with": ["bac-water"],
        },
    ),
    "glow-bpc-157-tb-500-ghk": (
        "A three-compound repair-research blend combining BPC-157, TB-500, and GHK-Cu.",
        {
            "overview": (
                "GLOW combines three compounds frequently studied together in tissue-repair research: "
                "BPC-157 (gastric-derived, studied for angiogenesis and repair signaling), TB-500 "
                "(a synthetic Thymosin Beta-4 fragment studied for cell migration), and GHK-Cu (a "
                "naturally occurring copper peptide studied in tissue remodeling)."
            ),
            "key_points": [
                "Three complementary repair-research compounds in one vial",
                "Combines a gastric-derived peptide, an actin-binding fragment, and a copper peptide",
                "One of the most commonly requested combination blends in this research category",
            ],
            "research_areas": [
                "Angiogenesis and repair signaling (BPC-157)",
                "Cell migration and actin regulation (TB-500)",
                "Tissue remodeling and copper-peptide signaling (GHK-Cu)",
            ],
            "pairs_with": ["klow-kpv-bpc-157-tb-500-ghk", "bpc-157-tb-500-wolverine", "bac-water"],
        },
    ),
    "klow-kpv-bpc-157-tb-500-ghk": (
        "A four-compound repair-research blend — GLOW plus the anti-inflammatory peptide KPV.",
        {
            "overview": (
                "KLOW builds on the GLOW blend (BPC-157, TB-500, GHK-Cu) by adding KPV, the C-terminal "
                "tripeptide of alpha-MSH studied for anti-inflammatory signaling without the "
                "melanogenic effects of its parent compound."
            ),
            "key_points": [
                "Four compounds in one vial: KPV, BPC-157, TB-500, GHK-Cu",
                "Adds anti-inflammatory research signaling to the GLOW combination",
                "KPV retains alpha-MSH's anti-inflammatory activity without pigmentation effects",
            ],
            "research_areas": [
                "Anti-inflammatory signaling (KPV)",
                "Angiogenesis and repair signaling (BPC-157)",
                "Cell migration and actin regulation (TB-500)",
                "Tissue remodeling and copper-peptide signaling (GHK-Cu)",
            ],
            "pairs_with": ["glow-bpc-157-tb-500-ghk", "bac-water"],
        },
    ),
    "cjc-no-dac-ipamorelin": (
        "A no-DAC CJC-1295 + Ipamorelin stack for pulsatile GH-release research.",
        {
            "overview": (
                "\"No DAC\" refers to CJC-1295 without Drug Affinity Complex — the modification that "
                "otherwise extends the compound's half-life. Without it, CJC-1295 behaves closer to "
                "native GHRH: a short half-life that produces a sharp, pulsatile GH-release signal, "
                "which researchers pair with Ipamorelin's selective ghrelin-receptor agonism."
            ),
            "key_points": [
                "CJC-1295 without DAC — short half-life, pulsatile release profile",
                "Paired with Ipamorelin for dual-pathway GH research",
                "A frequently referenced comparison point against DAC-modified GHRH analogs",
            ],
            "research_areas": [
                "Pulsatile vs. sustained GHRH receptor activation",
                "Dual-pathway GH secretagogue synergy",
            ],
            "faq": [
                {
                    "q": "What does \"no DAC\" mean?",
                    "a": "DAC (Drug Affinity Complex) is a modification that extends CJC-1295's "
                    "half-life by binding it to albumin in the bloodstream. Without it, the compound "
                    "clears faster and produces a sharper, more pulsatile GH-release signal — closer "
                    "to how endogenous GHRH behaves.",
                }
            ],
            "pairs_with": ["bac-water"],
        },
    ),
    "bpc-157": (
        "A gastric-derived pentadecapeptide studied for tissue repair and angiogenesis.",
        {
            "overview": (
                "BPC-157 (\"Body Protection Compound-157\") is a synthetic peptide based on a partial "
                "sequence found in human gastric juice. It's one of the most extensively studied peptides "
                "in tissue-repair research, with a large body of preclinical literature examining its "
                "role in angiogenesis and cell signaling."
            ),
            "key_points": [
                "Derived from a naturally occurring gastric protective protein sequence",
                "Extensively represented in preclinical repair/angiogenesis literature",
                "One of the most frequently stacked compounds in this catalog (see TB-500, GHK-Cu blends)",
            ],
            "research_areas": [
                "Angiogenesis (new blood vessel formation)",
                "Tissue repair signaling pathways",
                "Gastrointestinal protective mechanisms",
            ],
            "pairs_with": ["tb-500", "bpc-157-tb-500-wolverine", "ghk-cu", "bac-water"],
        },
    ),
    "tb-500": (
        "A synthetic Thymosin Beta-4 fragment studied for cell migration and wound-healing research.",
        {
            "overview": (
                "TB-500 is a synthetic version of the active region of Thymosin Beta-4, a naturally "
                "occurring protein present in nearly all human cells. It's studied primarily for its "
                "actin-binding properties, which researchers link to cell migration and wound-healing "
                "signaling."
            ),
            "key_points": [
                "Synthetic fragment of naturally occurring Thymosin Beta-4",
                "Actin-binding mechanism",
                "Frequently stacked with BPC-157 in repair-research protocols",
            ],
            "research_areas": [
                "Actin regulation and cell migration",
                "Wound-healing signaling pathways",
                "Angiogenesis research",
            ],
            "pairs_with": ["bpc-157", "bpc-157-tb-500-wolverine", "bac-water"],
        },
    ),
    "bpc-157-tb-500-wolverine": (
        "A pre-blended BPC-157 + TB-500 repair-research stack.",
        {
            "overview": (
                "Nicknamed \"Wolverine\" in the research community, this blend pre-combines BPC-157 and "
                "TB-500 — two of the most commonly co-studied repair-research peptides — in a single "
                "vial at a 1:1 ratio."
            ),
            "key_points": [
                "Pre-blended 1:1 BPC-157 + TB-500",
                "No separate reconstitution/mixing needed",
                "One of the most requested combination stacks in tissue-repair research",
            ],
            "research_areas": [
                "Combined angiogenesis and cell-migration signaling",
                "Comparative studies vs. either compound alone",
            ],
            "pairs_with": ["ghk-cu", "bac-water"],
        },
    ),
    "hcg-6000-units": (
        "Human chorionic gonadotropin, an LH-receptor agonist used in endocrine research.",
        {
            "overview": (
                "HCG (human chorionic gonadotropin) is a naturally occurring hormone that acts on the "
                "same receptor as luteinizing hormone (LH). It's a long-established reference compound "
                "in reproductive endocrinology research."
            ),
            "key_points": [
                "LH-receptor agonist",
                "Long-established reference compound in endocrine research",
                "Supplied as 6,000-unit lyophilized vials",
            ],
            "research_areas": [
                "LH-receptor signaling",
                "Reproductive endocrinology research models",
            ],
            "pairs_with": ["bac-water"],
        },
    ),
    "aod-9604": (
        "A modified hGH fragment (176-191) studied for lipid metabolism research.",
        {
            "overview": (
                "AOD-9604 is a modified fragment corresponding to amino acids 176-191 of human growth "
                "hormone — the region of the hGH molecule researchers have linked to lipid metabolism "
                "effects, isolated without the broader growth-promoting activity of full-length hGH."
            ),
            "key_points": [
                "Modified fragment of human growth hormone (176-191)",
                "Isolates the fat-metabolism-associated region of the hGH sequence",
                "Studied independently of full-length hGH's growth-promoting activity",
            ],
            "research_areas": [
                "Lipid metabolism pathways",
                "hGH fragment structure-activity research",
            ],
            "pairs_with": ["bac-water"],
        },
    ),
    "nad": (
        "Nicotinamide adenine dinucleotide, a coenzyme central to cellular energy metabolism research.",
        {
            "overview": (
                "NAD+ is a coenzyme found in every living cell, essential to redox reactions and cellular "
                "energy production. It's a central molecule in current longevity and mitochondrial "
                "function research, where declining NAD+ levels are studied in the context of cellular "
                "aging."
            ),
            "key_points": [
                "Essential coenzyme in cellular redox reactions",
                "Central molecule in current longevity/mitochondrial research",
                "Available in 500mg and 1000mg lyophilized vials",
            ],
            "research_areas": [
                "Cellular energy metabolism (redox reactions)",
                "Mitochondrial function research",
                "Cellular aging / longevity research models",
            ],
            "pairs_with": ["ss-31", "epithalon", "bac-water"],
        },
    ),
    "pt-141": (
        "A melanocortin receptor agonist studied for arousal-pathway research.",
        {
            "overview": (
                "PT-141 (bremelanotide) is a melanocortin receptor agonist, structurally related to "
                "Melanotan II. Unlike compounds that act on peripheral vascular pathways, PT-141 is "
                "studied for its activity within central melanocortin signaling."
            ),
            "key_points": [
                "Melanocortin receptor (MC3R/MC4R) agonist",
                "Structurally related to Melanotan II",
                "Studied for central (not peripheral vascular) signaling activity",
            ],
            "research_areas": [
                "Central melanocortin receptor signaling",
                "Comparative studies vs. Melanotan I/II",
            ],
            "pairs_with": ["mt-1", "mt-2", "bac-water"],
        },
    ),
    "igf1-lr3": (
        "A long-acting IGF-1 analog studied in anabolic cell-signaling research.",
        {
            "overview": (
                "IGF-1 LR3 is a modified analog of insulin-like growth factor 1 with an extended arginine "
                "substitution (\"Long R3\") that reduces its binding to IGF-binding proteins, giving it a "
                "meaningfully longer active half-life than native IGF-1 in research models."
            ),
            "key_points": [
                "Modified IGF-1 analog with reduced IGF-binding-protein affinity",
                "Extended half-life vs. native IGF-1",
                "Studied in anabolic and cell-proliferation signaling research",
            ],
            "research_areas": [
                "IGF-1 receptor signaling",
                "Cell proliferation and anabolic pathway research",
            ],
            "pairs_with": ["bac-water"],
        },
    ),
    "mots-c": (
        "A mitochondrial-derived peptide studied as an exercise-mimetic in metabolic research.",
        {
            "overview": (
                "MOTS-c is encoded within the mitochondrial genome rather than nuclear DNA — one of a "
                "small class of \"mitochondrial-derived peptides.\" It's studied in metabolic research "
                "for effects that resemble those induced by exercise, particularly around AMPK pathway "
                "activation."
            ),
            "key_points": [
                "Encoded by the mitochondrial (not nuclear) genome",
                "Studied as an exercise-mimetic in metabolic research",
                "Linked to AMPK pathway activation in preclinical literature",
            ],
            "research_areas": [
                "Mitochondrial-nuclear signaling",
                "AMPK pathway activation",
                "Exercise-mimetic metabolic research",
            ],
            "pairs_with": ["nad", "bac-water"],
        },
    ),
    "mt-1": (
        "Melanotan I, a melanocortin receptor agonist studied for melanogenesis research.",
        {
            "overview": (
                "Melanotan I is a synthetic analog of alpha-MSH, studied for its activity at the MC1R "
                "receptor — the pathway responsible for melanogenesis (melanin production). It's the "
                "more receptor-selective of the two Melanotan compounds studied in this space."
            ),
            "key_points": [
                "Synthetic alpha-MSH analog",
                "More MC1R-selective than Melanotan II",
                "Reference compound in melanogenesis research",
            ],
            "research_areas": [
                "MC1R receptor signaling",
                "Melanogenesis pathway research",
            ],
            "faq": [
                {
                    "q": "How is this different from Melanotan II (MT-2)?",
                    "a": "MT-1 is more selective for the MC1R receptor pathway linked to melanogenesis. "
                    "MT-2 engages a broader range of melanocortin receptors, which is why it's studied "
                    "in additional contexts beyond pigmentation (see PT-141, a related compound).",
                }
            ],
            "pairs_with": ["mt-2", "bac-water"],
        },
    ),
    "mt-2": (
        "Melanotan II, a broad-spectrum melanocortin receptor agonist.",
        {
            "overview": (
                "Melanotan II engages a broader set of melanocortin receptors than Melanotan I, which is "
                "why it's studied across a wider range of contexts — from melanogenesis to the central "
                "signaling pathways that PT-141 was later developed to target more selectively."
            ),
            "key_points": [
                "Broad-spectrum melanocortin receptor agonist",
                "Structural predecessor to PT-141",
                "Studied across melanogenesis and central signaling contexts",
            ],
            "research_areas": [
                "Melanocortin receptor signaling (MC1R, MC3R, MC4R)",
                "Melanogenesis pathway research",
                "Comparative studies vs. PT-141",
            ],
            "pairs_with": ["mt-1", "pt-141", "bac-water"],
        },
    ),
    # TODO(attorney-review): see the note on glp-1s. The overview previously
    # named the reference drug outright; that spelling must never appear in
    # public copy.
    "cagrilinitide": (
        "A metabolic-pathway research compound. Receptor activity and published "
        "literature are described in the research sections of this page.",
        {
            "overview": (
                "Cagrilinitide is studied as a long-acting amylin-receptor compound. Amylin and "
                "incretin receptors are distinct signalling systems, which is why this compound is "
                "frequently investigated alongside the incretin-class compounds in this catalog."
            ),
            "key_points": [
                "Long-acting amylin-receptor compound",
                "Distinct signalling pathway from incretin-class compounds",
                "Frequently co-studied with incretin-class compounds",
            ],
            "research_areas": [
                "Amylin receptor signalling",
                "Combined amylin and incretin pathway studies",
                "Comparative metabolic pathway research",
            ],
            "pairs_with": ["glp-1s", "glp-2t", "glp-3r", "bac-water"],
        },
    ),
    "ghk-cu": (
        "A naturally occurring copper peptide studied in tissue-remodeling research.",
        {
            "overview": (
                "GHK-Cu is a naturally occurring copper-binding peptide present in human plasma, saliva, "
                "and urine, at levels that decline with age. It's one of the most established compounds "
                "in tissue-remodeling and collagen-signaling research."
            ),
            "key_points": [
                "Naturally occurring copper-binding tripeptide",
                "Plasma levels decline with age — a frequent research reference point",
                "Well-established in tissue-remodeling literature",
            ],
            "research_areas": [
                "Copper-peptide signaling",
                "Tissue remodeling and collagen synthesis pathways",
                "Age-related decline studies",
            ],
            "pairs_with": ["ghk-cu-kpv", "bpc-157", "bac-water"],
        },
    ),
    "ghk-cu-kpv": (
        "A GHK-Cu + KPV blend combining copper-peptide and anti-inflammatory signaling research.",
        {
            "overview": (
                "This blend combines GHK-Cu, a copper peptide studied in tissue remodeling, with KPV, "
                "the anti-inflammatory C-terminal fragment of alpha-MSH — two compounds researchers "
                "often study together for complementary signaling pathways."
            ),
            "key_points": [
                "Combines copper-peptide and anti-inflammatory research compounds",
                "Pre-blended — no separate reconstitution needed",
            ],
            "research_areas": [
                "Copper-peptide tissue-remodeling signaling",
                "Anti-inflammatory pathway research (KPV)",
            ],
            "pairs_with": ["ghk-cu", "kpv", "bac-water"],
        },
    ),
    "ghrp-2": (
        "A ghrelin-receptor agonist studied as an early-generation GH secretagogue.",
        {
            "overview": (
                "GHRP-2 is one of the earlier-generation growth hormone-releasing peptides, a ghrelin "
                "receptor agonist studied alongside newer, more selective compounds like Ipamorelin as a "
                "comparison point for receptor selectivity and secondary hormonal effects."
            ),
            "key_points": [
                "Ghrelin receptor (GHS-R) agonist",
                "Early-generation GH secretagogue, frequently used as a research comparison point",
            ],
            "research_areas": [
                "Ghrelin receptor signaling",
                "Comparative GH secretagogue selectivity studies",
            ],
            "pairs_with": ["ghrp-6", "ipamorelin", "bac-water"],
        },
    ),
    # TODO(attorney-review): this tagline becomes Product.description, which
    # renders directly under the product name — i.e. in marketing voice. It
    # asserts a pronounced appetite-signalling effect, structurally the same
    # defect corrected on the GLP-class entries above. Copy left as authored
    # rather than rewritten unilaterally; ghrp-6 is NOT currently sellable
    # (no verified lyophilized supplier mapping), so nothing renders today.
    # Rewrite this before ghrp-6 is ever made sellable.
    "ghrp-6": (
        "A ghrelin-receptor agonist notable in research for its pronounced appetite-signaling effect.",
        {
            "overview": (
                "GHRP-6 is another early-generation ghrelin receptor agonist, studied alongside GHRP-2 "
                "and noted in the literature for a comparatively strong appetite-signaling effect — a "
                "distinguishing characteristic researchers use when comparing GH secretagogue compounds."
            ),
            "key_points": [
                "Ghrelin receptor (GHS-R) agonist",
                "Noted in literature for pronounced appetite-signaling activity",
            ],
            "research_areas": [
                "Ghrelin receptor signaling",
                "Appetite-pathway research",
                "Comparative GH secretagogue studies",
            ],
            "pairs_with": ["ghrp-2", "bac-water"],
        },
    ),
    "ta-1": (
        "Thymosin Alpha-1, a thymic-origin peptide studied in immune-modulation research.",
        {
            "overview": (
                "Thymosin Alpha-1 is derived from thymosin fraction 5, originally isolated from the "
                "thymus gland. It's one of the most established compounds in immune-modulation research, "
                "studied for its role in T-cell function."
            ),
            "key_points": [
                "Thymic-origin peptide",
                "Well-established in immune-modulation literature",
                "Studied for T-cell function effects",
            ],
            "research_areas": [
                "T-cell function and maturation",
                "Immune-modulation pathway research",
            ],
            "pairs_with": ["epithalon", "bac-water"],
        },
    ),
    "epithalon": (
        "A synthetic tetrapeptide studied in telomerase-activation and cellular-aging research.",
        {
            "overview": (
                "Epithalon (epitalon) is a synthetic tetrapeptide developed from research into the "
                "pineal gland's role in aging. It's studied primarily in the context of telomerase "
                "activity and cellular senescence."
            ),
            "key_points": [
                "Synthetic tetrapeptide",
                "Developed from pineal-gland aging research",
                "Studied in telomerase-activity and senescence research",
            ],
            "research_areas": [
                "Telomerase activity",
                "Cellular senescence research",
                "Pineal gland signaling studies",
            ],
            "pairs_with": ["nad", "ta-1", "bac-water"],
        },
    ),
    "kisspeptin": (
        "A neuropeptide studied as the upstream regulator of GnRH in reproductive endocrinology.",
        {
            "overview": (
                "Kisspeptin sits upstream of GnRH in the hypothalamic-pituitary-gonadal axis, making it a "
                "key reference molecule in reproductive endocrinology research over the past two decades."
            ),
            "key_points": [
                "Upstream regulator of GnRH release",
                "Central to modern hypothalamic-pituitary-gonadal axis research",
            ],
            "research_areas": [
                "GnRH pathway regulation",
                "Hypothalamic-pituitary-gonadal axis research",
            ],
            "pairs_with": ["bac-water"],
        },
    ),
    "kpv": (
        "The C-terminal tripeptide of alpha-MSH, studied for anti-inflammatory signaling without pigmentation effects.",
        {
            "overview": (
                "KPV is the smallest active fragment of alpha-MSH — just the C-terminal tripeptide. It "
                "retains alpha-MSH's anti-inflammatory signaling activity in research models without "
                "engaging the melanocortin receptors responsible for pigmentation."
            ),
            "key_points": [
                "Smallest active fragment of alpha-MSH",
                "Retains anti-inflammatory activity without pigmentation effects",
                "Frequently included in combination blends (see KLOW, GHK-Cu/KPV)",
            ],
            "research_areas": [
                "Anti-inflammatory signaling pathways",
                "Structure-activity research on alpha-MSH fragments",
            ],
            "pairs_with": ["ghk-cu-kpv", "klow-kpv-bpc-157-tb-500-ghk", "bac-water"],
        },
    ),
    "selank": (
        "A synthetic tuftsin analog studied in anxiolytic and nootropic research.",
        {
            "overview": (
                "Selank is a synthetic peptide developed from tuftsin, an endogenous immunomodulatory "
                "peptide. Russian pharmacological research has studied it extensively for anxiolytic and "
                "cognitive-modulation effects distinct from its parent compound's immune activity."
            ),
            "key_points": [
                "Synthetic analog developed from tuftsin",
                "Studied in anxiolytic and cognitive-modulation research",
                "Frequently referenced alongside Semax in nootropic-peptide literature",
            ],
            "research_areas": [
                "Anxiolytic pathway research",
                "Cognitive-modulation studies",
                "GABA and monoamine system interactions",
            ],
            "pairs_with": ["semax", "dsip", "bac-water"],
        },
    ),
    "semax": (
        "A synthetic ACTH(4-10) analog studied in cognitive and neuroprotective research.",
        {
            "overview": (
                "Semax is a synthetic peptide derived from ACTH(4-10), developed by Russian researchers "
                "and studied for neuroprotective and cognitive effects distinct from ACTH's hormonal "
                "activity — the modification removes the corticotropic effect while preserving central "
                "nervous system activity."
            ),
            "key_points": [
                "Synthetic ACTH(4-10) fragment analog",
                "Neuroprotective activity without corticotropic (hormonal) effects",
                "Extensively studied in Russian cognitive-research literature",
            ],
            "research_areas": [
                "Neuroprotective pathway research",
                "BDNF expression studies",
                "Cognitive-performance research models",
            ],
            "pairs_with": ["selank", "bac-water"],
        },
    ),
    "ss-31": (
        "A mitochondria-targeted peptide studied for oxidative-stress and mitochondrial-membrane research.",
        {
            "overview": (
                "SS-31 (elamipretide) is designed to concentrate in the inner mitochondrial membrane, "
                "where it's studied for its interaction with cardiolipin and its effects on mitochondrial "
                "oxidative stress — a mechanism distinct from most other peptides in this catalog."
            ),
            "key_points": [
                "Mitochondria-targeted peptide",
                "Studied for cardiolipin interaction in the inner mitochondrial membrane",
                "Distinct mechanism from GH- or receptor-agonist-class peptides",
            ],
            "research_areas": [
                "Mitochondrial membrane and cardiolipin interaction",
                "Oxidative stress research",
                "Cellular energy metabolism studies",
            ],
            "pairs_with": ["nad", "bac-water"],
        },
    ),
    "dsip": (
        "Delta sleep-inducing peptide, studied in sleep-regulation research.",
        {
            "overview": (
                "DSIP was first isolated from rabbit cerebral venous blood during studies on sleep "
                "regulation. Despite the name, its exact mechanism remains an active area of research — "
                "it's studied as much for its broader neuroendocrine signaling as for sleep specifically."
            ),
            "key_points": [
                "First isolated during sleep-regulation research",
                "Broader neuroendocrine signaling still an active research question",
            ],
            "research_areas": [
                "Sleep-regulation pathway research",
                "Neuroendocrine signaling studies",
            ],
            "pairs_with": ["selank", "bac-water"],
        },
    ),
    "bac-water": (
        "Bacteriostatic water — the standard sterile diluent for reconstituting lyophilized peptides.",
        {
            "overview": (
                "Bacteriostatic water is sterile water preserved with 0.9% benzyl alcohol, which inhibits "
                "bacterial growth across multiple draws from the same vial. It's the standard diluent "
                "used to reconstitute lyophilized (freeze-dried) peptide powder into solution for "
                "laboratory use."
            ),
            "key_points": [
                "Sterile water with 0.9% benzyl alcohol preservative",
                "Supports multiple draws from one vial without re-sterilizing",
                "The standard diluent for every lyophilized product in this catalog",
            ],
            "research_areas": [],
        },
    ),
}
