# Presentation only: consume verified bundle tables; never recompute analyses.
annual_reproduction_code <- function() paste(c(
  "from pathlib import Path",
  "import hashlib",
  "import json",
  "import pandas as pd",
  "",
  'root = Path("data")  # Run from the report folder',
  'manifest = json.loads((root / "bundle.json").read_text())',
  'for name, expected in manifest["files"].items():',
  "    actual = hashlib.sha256((root / name).read_bytes()).hexdigest()",
  "    if actual != expected:",
  '        raise ValueError(f"Bundle integrity failed: {name}")',
  "",
  'metrics = pd.read_csv(root / "metrics.csv")',
  'totals = metrics.loc[metrics["metric_type"].eq("group_total")]',
  'print(totals[["metric_id", "subject", "year", "value", "unit"]].to_string(index=False))',
  "",
  'changes = metrics.loc[metrics["metric_type"].eq("reference_change")]',
  'print(changes[["metric_id", "subject", "value", "unit"]].to_string(index=False))'
), collapse="\n")

code_disclosure <- function(code) paste0(
  '<details class="reproduction-code"><summary>Show code: inspect verified results</summary>',
  '<p>This executable Python example reads saved results; it is not the production analysis source. ',
  'Run it from the downloaded report folder with pandas installed.</p>',
  '<pre><code class="language-python">', esc(code), '</code></pre></details>'
)

document_section <- function(id, title, body) paste0(
  '<section class="document-section" id="', esc(id), '"><h2>',
  esc(title), '</h2>', body, '</section>'
)

document_chart <- function(plot, alt, note) paste0(
  '<figure>', chart_image(plot, alt, 8, 4.2),
  '<figcaption>', esc(note), '</figcaption></figure>'
)

document_navigation <- function(ids, titles) paste0(
  '<aside class="document-toc"><nav aria-label="Table of contents">',
  '<p>Contents</p>',
  paste(vapply(seq_along(ids), function(i) paste0(
    '<a href="#', esc(ids[i]), '">', esc(titles[i]), '</a>'
  ), character(1)), collapse=''),
  '</nav></aside>'
)

document_limits <- function(b) paste0(
  '<p>Notifications depend on testing, surveillance and reporting. ',
  'They are not a count of every infection. These annual comparisons do not ',
  'establish causes, clinical severity or statistical significance.</p>',
  '<p>Reference year: ', esc(b$cfg$reference_year),
  '. Reporting window: ', esc(paste(b$cfg$years, collapse='–')),
  '. This report does not calculate weekly alert levels, seasonal comparison ',
  'windows, age distributions or canton maps.</p>'
)

document_provenance <- function(b) {
  p <- presentation_profile(b)
  paste0(
    '<dl class="provenance-list"><dt>Audience</dt><dd>', esc(p$display_name),
    '</dd><dt>Presentation version</dt><dd>', esc(p$version),
    '</dd><dt>Snapshot</dt><dd><code>', esc(b$manifest$snapshot_id),
    '</code></dd></dl>',
    '<p><a href="provenance.json" download>Download request provenance</a> · ',
    '<a href="data/bundle.json" download>Download bundle manifest</a> · ',
    '<a href="methods.html">Methods and source traceability</a></p>'
  )
}

selected_coverage <- function(b) {
  d <- b$series
  ids <- intersect(
    c('dataset_id','topic','pathogen_class','source_system','year','value'),
    names(d)
  )
  d <- d[, ids, drop=FALSE]
  if(!'dataset_id' %in% names(d)) stop('Series lack dataset identifiers')
  groups <- split(d, d$dataset_id)
  rows <- lapply(groups, function(g) data.frame(
    Dataset=g$dataset_id[1],
    Disease=label_topic(b, g$topic[1]),
    Class=g$pathogen_class[1],
    First_year=min(g$year),
    Last_year=max(g$year),
    Annual_values=nrow(g),
    check.names=FALSE
  ))
  do.call(rbind, rows)
}

quality_document <- function(b) {
  q <- as.data.frame(table(b$checks$status))
  names(q) <- c('Result', 'Checks')
  paste0(
    html_table(q),
    '<p>Scope: checks saved with this selected report. Numerical checks use ',
    'the selected harmonised rows; registry metadata checks may include other ',
    'source records retained in the registry. SKIP is not PASS. ',
    'Blocking failures prevent report generation.</p>'
  )
}

audience_document_html <- function(b, navigation=TRUE) {
  p <- presentation_profile(b)
  technical <- p$layout == 'technical'
  sections <- list()
  add <- function(id, title, body) {
    sections[[length(sections)+1L]] <<- list(
      id=id, title=title, html=document_section(id, title, body)
    )
  }

  add('overview', if(technical) 'Data at a glance' else 'Situation at a glance',
      paste0(selection_intro(b),
             if(show_section(b, 'headline')) summary_cards(b) else ''))

  if(technical) {
    add('coverage', 'Selected data coverage', html_table(selected_coverage(b)))
    if(show_section(b, 'quality'))
      add('quality', 'Quality checks', quality_document(b))
    add('methods', 'Methods', paste0(
      '<p>Use the same selected annual national series throughout the reporting ',
      'window and reference year. Group sums respect the saved disease and ',
      'source exclusions. A reported annual total is preferred; otherwise ',
      'a complete compatible set of twelve months is required.</p>',
      '<p>Percentage change = (latest − reference) ÷ reference × 100. ',
      'Source definitions, selection decisions and record-level lineage are ',
      'available in the <a href="methods.html">companion methods report</a>.</p>'
    ))
  }

  if(show_section(b, 'group_totals'))
    add('totals', if(technical) 'Annual group totals' else 'Reported notification totals',
        document_chart(
          plot_group_totals(b), 'Annual totals for the selected disease groups',
          'Source: verified group totals. Counts describe notifications, not all infections.'
        ))

  if(show_section(b, 'group_index'))
    add('trends', if(technical) 'Group trends' else 'Changes versus the reference year',
        document_chart(
          plot_groups(b), 'Selected group trends relative to their baseline',
          paste('Each group is compared with its own', b$cfg$index_base_year,
                'total. This is not a seasonal alert classification.')
        ))

  if(show_section(b, 'change_table') || show_section(b, 'small_multiples'))
    add('diseases', if(technical) 'Disease-level results' else 'Disease monitoring table',
        paste0(
          if(show_section(b, 'small_multiples')) document_chart(
            plot_changes(b), 'Disease-specific reference-year changes',
            'Large percentage changes can start from small counts.'
          ) else '',
          if(show_section(b, 'change_table')) html_table(friendly_table(b)) else ''
        ))

  if(technical) {
    totals <- b$metrics[
      b$metrics$metric_type == 'group_total',
      c('metric_id','subject','year','value','unit')
    ]
    add('reproduction', 'Reproduce and inspect results',
        paste0(
          html_table(totals),
          code_disclosure(annual_reproduction_code()),
          '<p><a href="data/metrics.csv" download>Metrics CSV</a> · ',
          '<a href="data/lineage.csv" download>Calculation lineage CSV</a></p>'
        ))
  } else {
    add('interpretation', 'How to read this briefing', paste0(
      '<p>Read absolute notification counts alongside percentage changes. ',
      'Only the selected bacterial and viral datasets contribute to the displayed ',
      'comparison. An increase versus the reference year does not itself mean ',
      'an outbreak or an above-usual seasonal level.</p>',
      '<p>Source-specific release dates are listed in the ',
      '<a href="methods.html">methods and sources report</a>.</p>'
    ))
  }

  add('limitations', 'Limitations', document_limits(b))
  add('provenance', 'Provenance', document_provenance(b))
  ids <- vapply(sections, function(s) s$id, character(1))
  titles <- vapply(sections, function(s) s$title, character(1))
  title <- if(technical) 'Infectious disease surveillance data report'
           else 'Infectious disease situation report'

  paste0(
    presentation_open(b),
    if(navigation) report_navigation(b) else '',
    '<header class="document-header"><p class="eyebrow">', esc(p$display_name),
    ' · annual selected-data report</p><h1>', title, '</h1>',
    report_metadata(b), '</header><div class="document-layout">',
    document_navigation(ids, titles), '<main class="document-body">',
    paste(vapply(sections, function(s) s$html, character(1)), collapse='\n'),
    '</main></div></div>'
  )
}

# Preserve General public's existing rendering exactly.
findings_html_previous <- findings_html
findings_html <- function(b, navigation=TRUE) {
  if(presentation_profile(b)$layout == 'editorial')
    return(findings_html_previous(b, navigation))
  audience_document_html(b, navigation)
}

audience_document_pdf <- function(b) {
  p <- presentation_profile(b)
  technical <- p$layout == 'technical'
  heading <- function(title) cat('\n\n## ', title, '\n\n', sep='')
  table_out <- function(d) {
    print(knitr::kable(d, row.names=FALSE, format='pipe'))
    cat('\n\n')
  }
  title <- if(technical) 'Infectious disease surveillance data report'
           else 'Infectious disease situation report'
  cat('# ', title, '\n\n', sep='')
  cat('Audience: ', p$display_name, '. Annual selected-data report.\n\n', sep='')
  cat('Reporting window: ', paste(b$cfg$years, collapse='–'),
      '. Reference year: ', b$cfg$reference_year, '.\n\n', sep='')

  heading(if(technical) 'Data at a glance' else 'Situation at a glance')
  cat('Selected diseases: ',
      paste(label_topic(b, group_topics(b)), collapse=', '), '.\n\n', sep='')

  if(show_section(b, 'headline')) {
    subjects <- c('viral:main','bacterial:main','viral:sensitivity')
    subjects <- subjects[
      paste0(subjects, ':reference_change') %in% b$metrics$metric_id
    ]
    for(subject in subjects) {
      label <- switch(
        subject,
        'viral:main'='Viral notifications',
        'bacterial:main'='Bacterial notifications',
        'viral:sensitivity'=paste('Viral without', sensitivity_label(b))
      )
      cat('- ', label, ': ',
          format_pct(metric_value(b, paste0(subject, ':reference_change'))),
          ' in ', report_year(b), ' versus ', b$cfg$reference_year,
          '.\n', sep='')
    }
    cat('\n')
  }

  if(technical) {
    heading('Selected data coverage')
    coverage <- selected_coverage(b)
    # Full dataset identifiers remain in accompanying CSVs.
    coverage$Dataset <- NULL
    table_out(coverage)

    if(show_section(b, 'quality')) {
      heading('Quality checks')
      q <- as.data.frame(table(b$checks$status))
      names(q) <- c('Result', 'Checks')
      table_out(q)
      cat('Numerical checks cover selected rows; registry metadata checks may ',
          'include other retained registry records. SKIP is not PASS. ',
          'Blocking failures prevent generation.\n\n', sep='')
    }

    heading('Methods')
    cat('Compare the same selected annual national series across the configured ',
        'years. Group sums follow the saved disease and source exclusions. ',
        'A reported annual total is preferred; otherwise twelve complete ',
        'compatible months are required.\n\n', sep='')
    cat('Percentage change = (latest count - reference count) / reference count ',
        '* 100. See the companion [Methods and sources](methods.pdf) for ',
        'selection decisions and lineage.\n\n', sep='')
  }

  if(show_section(b, 'group_totals')) {
    heading(if(technical) 'Annual group totals' else 'Reported notification totals')
    print(plot_group_totals(b))
    cat('\n\nSource: verified group totals. Notifications are not all infections.\n\n')
  }
  if(show_section(b, 'group_index')) {
    heading(if(technical) 'Group trends' else 'Changes versus the reference year')
    print(plot_groups(b))
    cat('\n\nEach group is compared with its own ', b$cfg$index_base_year,
        ' total. This is not a seasonal alert classification.\n\n', sep='')
  }
  if(show_section(b, 'small_multiples') || show_section(b, 'change_table')) {
    heading(if(technical) 'Disease-level results' else 'Disease monitoring table')
    if(show_section(b, 'small_multiples')) print(plot_changes(b))
    cat('\n\n')
    if(show_section(b, 'change_table')) table_out(friendly_table(b))
    cat('Source: selected annual case series. Large percentage changes can ',
        'start from small counts.\n\n', sep='')
  }

  if(technical) {
    heading('Reproduce and inspect results')
    cat('The following Python example verifies the saved bundle and reads ',
        'its results. It is not the production analysis source. Run it from ',
        'the downloaded report folder with pandas installed.\n\n', sep='')
    cat('```python\n', annual_reproduction_code(), '\n```\n\n', sep='')
    cat('Detailed metric identifiers and input relationships are retained ',
        'in metrics.csv and lineage.csv.\n\n', sep='')
  } else {
    heading('How to read this briefing')
    cat('Read absolute counts alongside percentage changes. Only selected ',
        'datasets contribute. An increase versus the reference year does not ',
        'itself establish an outbreak or an above-usual seasonal level.\n\n', sep='')
  }

  heading('Limitations')
  cat('Notifications depend on testing, surveillance and reporting. ',
      'These descriptive comparisons do not establish causes, severity or ',
      'statistical significance. This report does not calculate weekly alert ',
      'levels, seasonal windows, age distributions or canton maps.\n\n', sep='')

  heading('Provenance')
  cat('Presentation version: ', p$version, '.\n\n', sep='')
  cat('Snapshot:\n\n```\n', b$manifest$snapshot_id, '\n```\n\n', sep='')
  cat('Keep provenance.json and the verified data bundle with this report. ',
      'Source definitions and record-level traceability are in the companion ',
      '[Methods and sources report](methods.pdf).\n\n', sep='')
}
