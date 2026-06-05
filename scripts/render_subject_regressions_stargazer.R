#!/usr/bin/env Rscript

suppressPackageStartupMessages(library(stargazer))

args <- commandArgs(trailingOnly = TRUE)
repo_dir <- if (length(args) >= 1) args[[1]] else "/root/sdb1/projects/Citations"
output_path <- if (length(args) >= 2) {
  args[[2]]
} else {
  file.path(repo_dir, "reports", "subjects", "trend_regression_stargazer_tables.html")
}

report_root <- file.path(repo_dir, "reports")

subjects <- data.frame(
  subject = c("economics", "ag_bio", "biochem", "physics"),
  label = c(
    "Economics",
    "Agricultural and Biological Sciences",
    "Biochemistry, Genetics, and Molecular Biology",
    "Physics and Astronomy"
  ),
  group = c("Economics", "Biology", "Biology", "Physics"),
  path = c(
    file.path(report_root, "economics", "event_time_summary.csv"),
    file.path(
      report_root,
      "subjects",
      "agricultural_and_biological_sciences",
      "hit_effects_counts_by_year",
      "event_time_summary.csv"
    ),
    file.path(
      report_root,
      "subjects",
      "biochemistry_genetics_and_molecular_biology",
      "hit_effects_counts_by_year",
      "event_time_summary.csv"
    ),
    file.path(
      report_root,
      "subjects",
      "physics_and_astronomy",
      "hit_effects_counts_by_year",
      "event_time_summary.csv"
    )
  ),
  stringsAsFactors = FALSE
)

frames <- lapply(seq_len(nrow(subjects)), function(i) {
  data <- read.csv(subjects$path[[i]], stringsAsFactors = FALSE)
  data$subject <- subjects$subject[[i]]
  data$subject_label <- subjects$label[[i]]
  data$group <- subjects$group[[i]]
  data
})

df <- do.call(rbind, frames)
df$post <- as.integer(df$event_time >= 0)
df$event_time_sq <- df$event_time * df$event_time
df$missing_rate <- with(
  df,
  (paper_author_hit_pairs - observed_pair_years) / paper_author_hit_pairs
)
df$subject <- factor(df$subject, levels = c("economics", "ag_bio", "biochem", "physics"))
df$group <- factor(df$group, levels = c("Economics", "Biology", "Physics"))

models <- list(
  "M1: Post only" = lm(
    mean_citations_zero_missing ~ post,
    data = df,
    weights = paper_author_hit_pairs
  ),
  "M2: Post + linear event time" = lm(
    mean_citations_zero_missing ~ post + event_time,
    data = df,
    weights = paper_author_hit_pairs
  ),
  "M3: Event-time controls + field group" = lm(
    mean_citations_zero_missing ~ post + event_time + event_time_sq + group,
    data = df,
    weights = paper_author_hit_pairs
  ),
  "M4: Event-time controls + field group + missingness" = lm(
    mean_citations_zero_missing ~ post + event_time + event_time_sq + group + missing_rate,
    data = df,
    weights = paper_author_hit_pairs
  ),
  "M5: Event-time controls + subject controls + missingness" = lm(
    mean_citations_zero_missing ~ post + event_time + event_time_sq + subject + missing_rate,
    data = df,
    weights = paper_author_hit_pairs
  )
)

covariate_labels <- c(
  "Post",
  "Event time",
  "Event time squared",
  "Biology",
  "Physics",
  "Agricultural and Biological Sciences",
  "Biochemistry, Genetics, and Molecular Biology",
  "Physics and Astronomy",
  "Missing rate",
  "Constant"
)

tables <- unlist(lapply(names(models), function(model_name) {
  capture.output(
    stargazer(
      models[[model_name]],
      type = "html",
      title = model_name,
      dep.var.labels = "Mean annual citations, zero-filled",
      covariate.labels = covariate_labels,
      digits = 4,
      single.row = FALSE,
      header = FALSE,
      keep.stat = c("n", "rsq", "adj.rsq", "f"),
      notes = "",
      notes.append = FALSE
    )
  )
}))

writeLines(tables, output_path)
