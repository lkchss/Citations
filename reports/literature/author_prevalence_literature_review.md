# Author Prevalence and Citation Spillovers: Literature Note

## Research Question

The working null is that annual citations to paper `j` depend only on the properties of paper `j`: its intrinsic quality, topic, venue, age profile, and other fixed or predictable characteristics of that paper. Under the null, citations to an author's other papers should not change citations to paper `j` once paper and calendar-year effects are absorbed, except through direct intellectual relatedness.

The alternative is an author-prevalence or author-attention channel: when an author's other papers accumulate attention, visibility, or status, that attention can spill over to citations of the author's existing papers that are not intellectually linked to the attention-generating work.

## Regression Specification

For each subject pool, estimate two models at the author-paper-year level:

```text
citations_jt = beta_1 accumulated_unrelated_citations_jt + FE_j + FE_t + epsilon_jt
```

```text
citations_jt = beta_1 accumulated_unrelated_citations_jt
             + beta_2 accumulated_related_citations_jt
             + FE_j + FE_t + epsilon_jt
```

Papers `i` and `j` are coded as related when `i = j`, `i` cites `j`, or `j` cites `i`. For a focal author-paper-year observation, accumulated unrelated citations are the author's lagged cumulative citations to papers outside that related set. Accumulated related citations are lagged cumulative citations to the focal paper and directly linked papers.

## Causal Interpretation with Paper Fixed Effects

The paper fixed effect `FE_j` removes all time-invariant paper-level determinants of citations: baseline quality, novelty, field placement, title, journal, author list attached to that paper, and other fixed attributes. The year fixed effect `FE_t` removes calendar-year shocks common to all papers, such as growth in publication volume, database coverage, or field-wide citation inflation.

With `FE_j` and `FE_t`, beta_1 is identified from within-paper changes over time in the author's unrelated citation stock. A causal interpretation is:

> Holding fixed the focal paper and common calendar-year conditions, beta_1 is the change in annual citations to paper `j` caused by an additional lagged citation to the author's unrelated body of work.

This interpretation requires a strong conditional exogeneity assumption: absent the change in author prevalence, paper `j` would not have experienced a differential citation change correlated with the author's unrelated citation stock. The main threats are time-varying author productivity, new appointments or prizes, coauthor network expansion, topic-level shocks not absorbed by year effects, and reverse causality through broad author visibility. The second regression helps separate broad author attention from direct intellectual proximity by adding accumulated related citations, but it does not by itself eliminate all time-varying author-level confounding.

Empirically, a positive beta_1 after controlling for related citations is evidence against the strict paper-properties-only null. It is most naturally interpreted as an author-level attention, status, or reputation spillover to already published unrelated work.

## Literature Map

### Cumulative Advantage and the Matthew Effect

Merton's Matthew effect frames scientific recognition as a cumulative process in which already visible scientists receive disproportionate attention and credit relative to equally valuable contributions by less visible scientists [@merton1968matthew; @merton1988matthew]. Price formalized citation accumulation as a cumulative-advantage process in bibliometrics [@price1976cumulative]. Later network models, including preferential attachment, provide a general mechanism by which initially small citation advantages can compound into skewed citation distributions [@barabasi1999emergence].

This literature motivates the null directly. If citations only measure the intrinsic properties of a paper, unrelated author-level citation stocks should not predict future citations to that paper. If cumulative advantage operates through authors, the unrelated stock should matter.

### Paper-Level Citation Dynamics

Paper-level citation models emphasize that citation histories reflect a combination of age, accumulated citations, and latent paper fitness. Wang, Song, and Barabasi show that individual papers follow regular citation life cycles with paper-specific fitness and aging components [@wang2013quantifying]. This supports using paper fixed effects: paper-specific fitness is precisely the confound the design is trying to absorb.

At the same time, citation dynamics models often include cumulative citation terms. That creates a risk that citation persistence within the focal paper is mistaken for an author-prevalence effect. This is why the proposed design excludes directly related papers from the unrelated stock and then separately controls for accumulated related citations.

### Reputation, Status, and Author Visibility

Petersen et al. explicitly model how an author's reputation contributes to a paper's citation rate, especially for younger or less independently established publications [@petersen2014reputation]. Simcoe and Waguespack use a natural experiment in name disclosure to separate status, quality, and attention, showing how status can alter attention conditional on underlying quality [@simcoe2011status]. Brogaard et al. study the causal effect of fame on citations using author-order variation, providing direct evidence that author fame can affect citation outcomes [@brogaard2024fame].

These papers provide the closest precedent for interpreting beta_1 as an author-attention or author-status parameter rather than a paper-quality parameter.

### Shocks to Scientific Prominence

Azoulay, Graff Zivin, and Wang exploit premature deaths of superstar scientists to estimate spillovers from prominent researchers to collaborators and nearby intellectual areas [@azoulay2010superstar]. Mazloumian et al. study citation boosts around landmark papers and Nobel Prize winners, finding that recognition of a major contribution can raise attention to a scientist's broader body of work [@mazloumian2011citation]. These designs are useful analogues for the planned "big hit" analysis: a major success can be treated as a shock to author prevalence, and older unrelated papers can be used to test whether attention spills backward across the author's portfolio.

### Social Influence in Citation Choices

Lynn studies citation behavior as social diffusion and shows that citation accumulation can depend on the social position of citing audiences and disciplinary boundaries [@lynn2014diffusing]. Siler et al. examine repeat authorship and cumulative advantage in scholarly journals, including economics journals, and show that publication and citation advantages can vary by field and journal setting [@siler2022cumulative]. Aksnes, Langfeldt, and Wouters review why citations should not be read as pure measures of research quality, emphasizing that citations reflect multiple social, cognitive, and evaluative processes [@aksnes2019citations].

These papers justify estimating the model separately by subject pool. The size and interpretation of beta_1 may differ between economics, biology, and physics because citation practices, coauthorship norms, and field boundaries differ.

## Design Implications

1. The core regression is a direct test of the paper-properties-only null.
2. Paper fixed effects are essential because they absorb fixed paper quality and paper-level citation fitness.
3. Year fixed effects are necessary but not sufficient; later versions should consider paper-age controls, author-year controls, field-year controls, or event-study specifications around large hits.
4. The unrelated citation stock should be lagged to avoid mechanically including year-`t` citations in both sides of the regression.
5. Related citations should be included as a separate control because direct intellectual links are a different mechanism from author prevalence.
6. The strongest causal design will come from author-level shocks, such as big-hit publications, awards, or other sharp visibility events, applied to pre-existing unrelated papers.

