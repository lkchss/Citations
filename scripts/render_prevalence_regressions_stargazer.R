#!/usr/bin/env Rscript

suppressPackageStartupMessages(library(stargazer))

args <- commandArgs(trailingOnly = TRUE)
data_root <- if (length(args) >= 1) args[[1]] else "/root/sdb1/openalex/subjects/prevalence_regressions"
repo_dir <- if (length(args) >= 2) args[[2]] else "/root/sdb1/projects/Citations"
output_path <- if (length(args) >= 3) {
  args[[3]]
} else {
  file.path(repo_dir, "reports", "subjects", "prevalence_regression_stargazer_tables.html")
}

subjects <- data.frame(
  subject = c(
    "economics_econometrics_and_finance",
    "agricultural_and_biological_sciences",
    "biochemistry_genetics_and_molecular_biology",
    "physics_and_astronomy"
  ),
  label = c(
    "Economics",
    "Agricultural and Biological Sciences",
    "Biochemistry, Genetics, and Molecular Biology",
    "Physics and Astronomy"
  ),
  stringsAsFactors = FALSE
)

tables <- c()
summaries <- list()

for (i in seq_len(nrow(subjects))) {
  subject <- subjects$subject[[i]]
  label <- subjects$label[[i]]
  path <- file.path(data_root, subject, "paper_author_year_prevalence_regression.csv.gz")
  if (!file.exists(path)) {
    next
  }

  df <- read.csv(gzfile(path), stringsAsFactors = FALSE)
  df$work_id <- factor(df$work_id)
  df$year <- factor(df$year)

  model_unrelated <- lm(
    citations_jt ~ accumulated_unrelated_citations_jt + work_id + year,
    data = df
  )
  model_related <- lm(
    citations_jt ~ accumulated_unrelated_citations_jt +
      accumulated_related_citations_jt + work_id + year,
    data = df
  )

  tables <- c(
    tables,
    capture.output(
      stargazer(
        model_unrelated,
        model_related,
        type = "html",
        title = label,
        dep.var.labels = "Citations to paper j in year t",
        column.labels = c("Unrelated stock", "Unrelated + related stocks"),
        covariate.labels = c(
          "Accumulated unrelated citations j,t",
          "Accumulated related citations j,t"
        ),
        omit = c("work_id", "year"),
        omit.labels = c("Paper fixed effects", "Year fixed effects"),
        omit.stat = c("ser", "f"),
        digits = 4,
        header = FALSE,
        notes = "",
        notes.append = FALSE
      )
    )
  )

  summaries[[length(summaries) + 1]] <- data.frame(
    subject = label,
    observations = nrow(df),
    papers = length(unique(df$work_id)),
    authors = length(unique(df$author_id)),
    mean_citations_jt = mean(df$citations_jt),
    mean_accumulated_unrelated = mean(df$accumulated_unrelated_citations_jt),
    mean_accumulated_related = mean(df$accumulated_related_citations_jt),
    stringsAsFactors = FALSE
  )
}

if (length(summaries) > 0) {
  summary_df <- do.call(rbind, summaries)
  tables <- c(
    capture.output(
      stargazer(
        summary_df,
        type = "html",
        title = "Regression Data Summary",
        summary = FALSE,
        digits = 4,
        header = FALSE
      )
    ),
    tables
  )
}

writeLines(tables, output_path)
