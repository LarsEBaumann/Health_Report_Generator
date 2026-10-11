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
  'windows, age distributions or canton maps.</p>',
  '<p>Recent years can still be revised by the publisher as late notifications arrive; ',
  'the snapshot identifier below pins exactly which release was used.</p>',
  '<p>', esc(quality_sentence(b)), '</p>'
)

document_provenance <- function(b) {
  p <- presentation_profile(b)

  commit <- Sys.getenv("GITHUB_SHA", unset = "")
  if (!nzchar(commit)) {
    commit <- "not recorded"
  }

  paste0(
    '<dl class="provenance-list"><dt>Audience</dt><dd>', esc(p$display_name),
    '</dd><dt>Presentation version</dt><dd>', esc(p$version),
    '</dd><dt>Snapshot</dt><dd><code>', esc(b$manifest$snapshot_id),
    '</code></dd><dt>Rendering code version</dt><dd><code>', esc(commit),
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

  if(p$layout == 'dashboard')
    add('monitoring', 'Monitoring summary', monitoring_summary(b))

  if(technical) {
    add('parameters', 'Effective parameters and filters', effective_parameters_table(b))
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

# ---------------------------------------------------------------------------
# Phase 5: parameter-driven audience content and embedded provenance.
# Everything below reads saved bundle tables or the provenance record written by
# publish.py; nothing recalculates statistics.
# ---------------------------------------------------------------------------
read_provenance <- function(path='provenance.json') {
  if(!file.exists(path)) return(NULL)
  jsonlite::fromJSON(path, simplifyVector=FALSE)
}

# Machine-readable provenance inside every HTML output. "</" is escaped so the
# JSON cannot terminate the script element.
provenance_script <- function(path='provenance.json') {
  if(!file.exists(path)) return('')
  json <- paste(readLines(path, warn=FALSE, encoding='UTF-8'), collapse='\n')
  json <- gsub('</', '<\\/', json, fixed=TRUE)
  paste0('<script type="application/json" id="report-provenance">', json, '</script>')
}

detail_level <- function(b) presentation_profile(b)$detail_level

check_counts <- function(b) {
  s <- toupper(as.character(b$checks$status))
  list(pass=sum(s=='PASS'), warn=sum(s=='WARN'), skip=sum(s=='SKIP'), fail=sum(s=='FAIL'), total=length(s))
}

# Plain-language and operational translations of the same quality results.
quality_sentence <- function(b) {
  q <- check_counts(b)
  if(detail_level(b) == 'plain_language') {
    paste0('Before this summary was made, the data went through ', q$total,
           ' automatic checks. ', q$pass, ' passed. ', q$warn,
           ' raised a warning that a person needs to interpret, and ', q$skip,
           ' could not be applied to this kind of data. Any serious failure would have stopped the report from being published.')
  } else {
    paste0(q$total, ' automated checks on this data release: ', q$pass, ' PASS, ', q$warn,
           ' WARN (needs interpretation), ', q$skip, ' SKIP (not applicable; not a pass), ',
           q$fail, ' FAIL. Blocking failures prevent publication.')
  }
}

provenance_summary <- function(b) {
  pr <- read_provenance()
  row <- function(k, v) paste0('<dt>', esc(k), '</dt><dd>', v, '</dd>')
  p <- presentation_profile(b)
  items <- c(row('Audience profile', esc(paste0(b$cfg$id, ' (', p$display_name, ', ', p$layout, ', ', p$detail_level, ')'))),
             row('Data snapshot', paste0('<code>', esc(b$manifest$snapshot_id), '</code>')))
  if(!is.null(pr)) {
    rng <- function(x) if(is.null(x)) 'not recorded' else esc(paste(unique(substr(unlist(x), 1, 10)), collapse=' to '))
    items <- c(items,
      row('Source', esc(pr$data$publisher)),
      row('Publisher release dates', rng(pr$data$publishing_date_range)),
      row('Downloaded from the API', rng(pr$data$retrieved_at_utc_range)),
      row('Input root', paste0('<code>', esc(if(is.null(pr$data$canonical_root)) pr$data$snapshot_manifest else pr$data$canonical_root), '</code>')),
      row('Filters', esc(paste0(pr$filters$geography, ' · ', paste(unlist(pr$filters$years), collapse='–'),
                                ' vs ', pr$filters$reference_year, ' · measure: ', paste(unlist(pr$filters$measures_preferred), collapse=', '),
                                ' · excluded from group sums: ', paste(label_topic(b, unlist(pr$filters$exclude_from_group_totals)), collapse=', '),
                                ' · sensitivity comparison without: ', paste(label_topic(b, unlist(pr$filters$sensitivity_exclude)), collapse=', ')))),
      row('Code version', paste0('<code>', esc(if(is.null(pr$code$git_commit)) 'not recorded' else pr$code$git_commit), '</code>',
                                 if(isFALSE(pr$code$git_worktree_clean)) ' (uncommitted changes present)' else '')),
      row('Rendered', esc(pr$rendered_at_utc)))
  }
  paste0('<dl class="provenance-list">', paste(items, collapse=''), '</dl>',
         '<p><a href="provenance.json" download>Download provenance (JSON)</a> · ',
         '<a href="data/stakeholder.json" download>Audience parameters</a> · ',
         '<a href="data/bundle.json" download>Bundle manifest</a> · ',
         '<a href="methods.html">Methods and source traceability</a></p>',
         '<p class="table-note">The same record is embedded in this page as ',
         '<code>&lt;script type="application/json" id="report-provenance"&gt;</code>.</p>')
}
document_provenance <- function(b) provenance_summary(b)

# Operational monitoring: largest absolute and relative changes with counts, and
# a small-number caution. The threshold is a display rule, not a statistical test.
SMALL_COUNT <- 20
monitoring_table <- function(b) {
  d <- friendly_changes(b)
  d$Difference <- d$Latest - d$Baseline
  d <- d[order(abs(d$Difference), decreasing=TRUE), ]
  caution <- ifelse(pmin(d$Baseline, d$Latest) < SMALL_COUNT, 'Small numbers: interpret with caution', '')
  fmt <- function(x) format(x, big.mark=',', scientific=FALSE, trim=TRUE)
  out <- data.frame(Disease=d$Disease, Reference=fmt(d$Baseline), Latest=fmt(d$Latest),
                    Difference=ifelse(d$Difference > 0, paste0('+', fmt(d$Difference)), fmt(d$Difference)),
                    Change=format_pct(d$Change, 1), Note=caution, check.names=FALSE)
  names(out)[2:3] <- c(paste('Cases', b$cfg$reference_year), paste('Cases', report_year(b)))
  if(all(out$Note == '')) out$Note <- NULL
  out
}
monitoring_summary <- function(b) {
  d <- friendly_changes(b); d$Difference <- d$Latest - d$Baseline
  up <- d[d$Difference > 0, ]; up <- up[order(up$Difference, decreasing=TRUE), ]
  down <- d[d$Difference < 0, ]; down <- down[order(down$Difference), ]
  li <- function(x) if(!nrow(x)) '<li>None</li>' else paste0('<li><strong>', esc(x$Disease), '</strong>: ',
        format(x$Baseline, big.mark=','), ' → ', format(x$Latest, big.mark=','), ' cases (', format_pct(x$Change), ')</li>', collapse='')
  paste0('<div class="monitoring-grid"><div><h3>Largest increases in reported cases</h3><ul>', li(head(up, 3)),
         '</ul></div><div><h3>Largest decreases</h3><ul>', li(head(down, 3)), '</ul></div></div>',
         '<p class="table-note">Ranked by absolute difference in notified cases, ', report_year(b), ' versus ', b$cfg$reference_year,
         '. Scope: ', if(b$cfg$geography=='CHFL') 'Switzerland and Liechtenstein combined' else 'Switzerland',
         ' national totals. Canton-level breakdowns are not part of this release because they are not available for every selected disease. ',
         'A change versus the reference year is not an outbreak signal or seasonal threshold.</p>',
         html_table(monitoring_table(b)),
         '<p class="table-note">Diseases with fewer than ', SMALL_COUNT, ' cases in either year are flagged as small numbers',
         if(all(pmin(d$Baseline, d$Latest) >= SMALL_COUNT)) '; none of the selected diseases is below that level in this release.' else '.', '</p>',
         '<p class="table-note">', esc(quality_sentence(b)), ' <a href="methods.html#selection">Selection decisions</a></p>')
}

effective_parameters_table <- function(b) {
  c <- b$cfg
  v <- function(x) paste(unlist(x), collapse=', ')
  d <- data.frame(Parameter=c('Stakeholder id','Geography','Reporting years','Reference year','Index base year',
                              'Preferred measures','Classes compared','Excluded from group sums','Sensitivity exclusion',
                              'Source priority','Sources summed in groups','Dimension filters','Sections shown','Presentation'),
                  Value=c(c$id, c$geography, v(c$years), c$reference_year, c$index_base_year, v(c$measures_preferred),
                          v(c$classes_in_main_comparison), v(c$exclude_from_group_totals), v(c$sensitivity_exclude),
                          v(c$source_priority), v(c$group_source_systems),
                          if(length(c$dimension_filters)) paste(vapply(names(c$dimension_filters), function(k)
                            paste0(k, ': ', paste(names(c$dimension_filters[[k]]$values), unlist(c$dimension_filters[[k]]$values), sep='=', collapse=';')),
                            character(1)), collapse=' | ') else 'none',
                          v(c$outputs), paste(presentation_profile(b)$layout, presentation_profile(b)$detail_level, sep=' / ')),
                  check.names=FALSE)
  paste0(html_table(d), '<p class="table-note">Source: <a href="data/stakeholder.json" download>stakeholder.json</a>, ',
         'validated against workflow/config.schema.json. Audiences differ only in these parameters.</p>')
}

# Public (editorial) additions: translate uncertainty instead of hiding it.
public_explainer <- function(b) {
  excluded <- paste(label_topic(b, b$cfg$exclude_from_group_totals), collapse=' and ')
  sens <- metric_value(b, 'viral:sensitivity:reference_change')
  sens_text <- if(length(b$cfg$sensitivity_exclude) && !is.na(sens)) paste0(
    '<li><strong>One disease can dominate a group.</strong> Without ', esc(sensitivity_label(b)),
    ', the change for viral diseases is ', format_pct(sens), ' instead of ',
    format_pct(metric_value(b, 'viral:main:reference_change')), '. These data show where the change is, not why it happened.</li>') else ''
  paste0(
    '<section class="chart-panel full plain-language" id="how-sure"><h2>How sure can we be?</h2><ul>',
    '<li><strong>These are reported cases, not all infections.</strong> Many people with mild illness never see a doctor or get tested, so the real number of infections is higher.</li>',
    '<li><strong>More testing finds more cases.</strong> A rise can mean the disease spread more, that more people were tested, or both. These numbers alone cannot tell which.</li>',
    sens_text,
    '<li><strong>Small numbers jump around.</strong> When a disease has only a few cases, a small change can look like a big percentage.</li>',
    '<li><strong>Recent numbers can still change.</strong> The Federal Office of Public Health may update counts for recent years as late reports arrive.</li>',
    '<li><strong>What is left out.</strong> ', esc(excluded), ' are not added to the group totals, and estimates from the doctors’ sample network (Sentinella) are not mixed with confirmed reports.</li>',
    '</ul><p>', esc(quality_sentence(b)), '</p>',
    '<p>This summary describes what was reported. It does not say whether a change is due to chance, and it does not explain causes. ',
    'If you are worried about an illness, talk to a doctor.</p></section>',
    '<section class="chart-panel full" id="provenance"><h2>Where this comes from</h2>', provenance_summary(b), '</section>')
}
audience_extras <- function(b) if(presentation_profile(b)$layout == 'editorial') public_explainer(b) else ''

# Lightweight, dependency-free interactivity for every HTML audience:
# filter any report table and sort by clicking a column heading.
interactive_tables_script <- function() paste0('<script>', "
(function(){
  function num(t){var x=t.replace(/[,%+\\s]/g,'').replace('\\u2212','-');return x!==''&&!isNaN(x)?parseFloat(x):null;}
  document.querySelectorAll('table.report-table').forEach(function(tbl,ti){
    var wrap=tbl.parentNode, body=tbl.tBodies[0]; if(!body) return;
    var input=document.createElement('input'); input.type='search'; input.className='table-filter';
    input.placeholder='Filter rows'; input.setAttribute('aria-label','Filter table rows');
    wrap.parentNode.insertBefore(input,wrap);
    input.addEventListener('input',function(){var q=input.value.toLowerCase();
      Array.prototype.forEach.call(body.rows,function(r){r.style.display=r.textContent.toLowerCase().indexOf(q)>-1?'':'none';});});
    Array.prototype.forEach.call(tbl.tHead?tbl.tHead.rows[0].cells:[],function(th,ci){
      th.tabIndex=0; th.className+=' sortable'; th.title='Sort by this column'; var asc=true;
      function sort(){var rows=Array.prototype.slice.call(body.rows);
        rows.sort(function(a,b){var x=a.cells[ci].textContent.trim(),y=b.cells[ci].textContent.trim(),nx=num(x),ny=num(y);
          var c=(nx!==null&&ny!==null)?nx-ny:x.localeCompare(y);return asc?c:-c;});
        rows.forEach(function(r){body.appendChild(r);}); th.setAttribute('aria-sort',asc?'ascending':'descending'); asc=!asc;}
      th.addEventListener('click',sort); th.addEventListener('keydown',function(e){if(e.key==='Enter')sort();});
    });
  });
})();", '</script>')
