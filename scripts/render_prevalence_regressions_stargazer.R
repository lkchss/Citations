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

default_subjects <- data.frame(
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

label_subject <- function(subject) {
  known <- default_subjects$label[default_subjects$subject == subject]
  if (length(known) == 1) {
    return(known)
  }
  words <- strsplit(gsub("_", " ", subject), " ")[[1]]
  paste(toupper(substr(words, 1, 1)), substring(words, 2), sep = "", collapse = " ")
}

subject_paths <- list.files(data_root, pattern = "paper_author_year_prevalence_regression.csv.gz$", recursive = TRUE, full.names = TRUE)
if (length(subject_paths) > 0) {
  discovered <- basename(dirname(subject_paths))
  subjects <- data.frame(
    subject = discovered,
    label = vapply(discovered, label_subject, character(1)),
    stringsAsFactors = FALSE
  )
} else {
  subjects <- default_subjects
}

tables <- c()
summaries <- list()

twoway_within <- function(values, paper_group, year_group, tolerance = 1e-10, max_iter = 200) {
  residual <- values - mean(values)
  for (iteration in seq_len(max_iter)) {
    previous <- residual
    residual <- residual - ave(residual, paper_group, FUN = mean)
    residual <- residual - ave(residual, year_group, FUN = mean)
    if (max(abs(residual - previous)) < tolerance) {
      break
    }
  }
  residual
}

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
  paper_group <- df$work_id
  year_group <- df$year
  regression_df <- data.frame(
    citations_jt_fe = twoway_within(df$citations_jt, paper_group, year_group),
    accumulated_unrelated_citations_jt_fe = twoway_within(
      df$accumulated_unrelated_citations_jt,
      paper_group,
      year_group
    ),
    accumulated_related_citations_jt_fe = twoway_within(
      df$accumulated_related_citations_jt,
      paper_group,
      year_group
    )
  )

  model_unrelated <- lm(
    citations_jt_fe ~ accumulated_unrelated_citations_jt_fe + 0,
    data = regression_df
  )
  model_related <- lm(
    citations_jt_fe ~ accumulated_unrelated_citations_jt_fe +
      accumulated_related_citations_jt_fe + 0,
    data = regression_df
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
        omit.stat = c("ser", "f"),
        digits = 4,
        header = FALSE,
        add.lines = list(
          c("Paper fixed effects", "Absorbed", "Absorbed"),
          c("Year fixed effects", "Absorbed", "Absorbed")
        ),
        notes = "Variables are residualized using iterative two-way demeaning by paper and year before estimation.",
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
