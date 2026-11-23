---
name: grafana-dashboard-standards
description: "Grafana dashboard standards: USE, RED and the Four Golden Signals, visual hierarchy, panel choice, sprawl control, query performance, and a maturity model. Use when building or reviewing a dashboard or judging whether a panel earns its place."
---
# Grafana Dashboard Best Practices

A comprehensive guide to creating effective, maintainable, and scalable Grafana dashboards based on official Grafana documentation and community best practices.

## Table of Contents

1. [Foundational Principles](#foundational-principles)
2. [Observability Methodologies](#observability-methodologies)
3. [Dashboard Design Guidelines](#dashboard-design-guidelines)
4. [Visual Hierarchy and Accessibility](#visual-hierarchy-and-accessibility)
5. [Panel Selection and Visualization Types](#panel-selection-and-visualization-types)
6. [Organization and Navigation](#organization-and-navigation)
7. [Management and Maintenance](#management-and-maintenance)
8. [Performance Optimization](#performance-optimization)
9. [Maturity Model](#maturity-model)
10. [Dashboard Review and Pre-Provisioning Audit](#dashboard-review-and-pre-provisioning-audit)

---

## Foundational Principles

### Know Your Purpose

Every dashboard should have a clear purpose. Ask yourself:

- **What story are you trying to tell?** Dashboards should present data in a logical progression (large to small, general to specific)
- **What question does this dashboard answer?** If it doesn't answer a question or tell a story, it shouldn't exist
- **Who is the audience?** Different roles have different needs:
  - Engineers prioritize system performance metrics
  - Product managers focus on user interaction data
  - Business stakeholders need high-level KPIs

### Reduce Cognitive Load

Design dashboards to minimize the mental effort required to interpret them:

- Graphs should be self-explanatory to viewers unfamiliar with the system
- Use clear labels and descriptions
- Avoid information overload - focus on what matters
- Include only the most relevant metrics that help make decisions quickly

### Consistency is Key

Once you establish design guidelines:

- Document them and share with your team
- Use template variables to maintain consistency
- Consider using scripting libraries (grafonnet, grafanalib) for programmatic dashboard generation
- Apply consistent naming conventions across all dashboards

---

## Observability Methodologies

Before creating dashboards, adopt one of these established monitoring strategies:

### USE Method (Infrastructure-Focused)

Best for resource-level dashboards monitoring hardware and infrastructure health (hosts, CPUs, memory, disks, network interfaces, worker pools), rather than request-driven application traffic:

- **Utilization**: Percentage of time or capacity the resource is busy
- **Saturation**: Work queue length, wait time, or system load beyond capacity
- **Errors**: Count of resource error events

*"The USE method tells you how happy your machines are"*

### RED Method (Service-Focused)

Best for request-driven services and stateless HTTP/gRPC APIs:

- **Rate**: Requests per second (overall and split by bounded labels such as route template or method)
- **Errors**: Failing request rate or **error ratio** (failing requests as a share of total traffic, so thresholds stay meaningful as load changes)
- **Duration**: Latency **distribution** over time (percentiles such as p50, p95, p99 and/or a histogram heatmap — never a single average, which hides tail latency)

*"The RED method tells you how happy your users are"*

**RED Method Dashboard Pattern:**

- Request and error rates on the left
- Latency duration on the right
- One row per service
- Row order reflects data flow

### Four Golden Signals

Comprehensive approach for user-facing systems:

- **Latency**: Time taken to service a request
- **Traffic**: Demand on your system (requests per second)
- **Errors**: Rate of failing requests
- **Saturation**: How full your service is (CPU, memory, I/O)

Choose the methodology that best fits your use case, document it, and maintain consistency across your dashboard ecosystem.

---

## Dashboard Design Guidelines

### Naming and Documentation

**Dashboard and Panel Titles:**

- Give both the dashboard and every panel a specific, self-explanatory title (e.g., `Acme Order API — RED`, `Request Rate by Route`), never Grafana's untouched defaults (`New dashboard`, `Panel Title`) or bare single-word labels (`latency`, `errors`) that omit what is measured
- Treat clone suffixes in titles (`copy`, `copy 1`, `v2`, `backup`, `- old`, or per-environment copies) as a direct **symptom of dashboard sprawl** — someone duplicated a dashboard in the UI instead of parameterizing a single dashboard with template variables or URL links
- Prefix experimental dashboards with `TEST` or `TMP` and delete them once the experiment ends
- Include team or owner metadata and relevant tags for discovery

**Documentation:**

- Add Text panels explaining the dashboard's purpose and usage
- Document individual panels with descriptions (visible on hover)
- Include links to runbooks or related documentation
- Specify the data sources and refresh intervals

### Meaningful Use of Color

- **Apply consistent color conventions**:
  - Blue/Green for good/normal values
  - Yellow/Orange for warnings
  - Red for critical/error states
- **Use thresholds** to automatically color code values
- **Avoid red-green combinations** for colorblind accessibility
- **Use saturated, distinct colors** to draw attention to important metrics

### Graph and Visualization Best Practices

**Axes and Scaling:**

- Normalize axes for fair comparisons (e.g., use percentages instead of raw numbers when comparing resources)
- Use both Y-axes when displaying metrics with different units or scales
- Set appropriate min/max values to avoid misleading visualizations

**Graph Types:**

- **Avoid stacking graphs** - stacked graphs can hide important data
- Use time series for temporal trends and patterns
- Use stat panels for single value snapshots
- Use gauges to show values relative to min/max thresholds

**Data Presentation and Units:**

- Configure an explicit semantic `unit` (`fieldConfig.defaults.unit`) on every numeric panel (`reqps` or `ops` for request and error rates, `percentunit` or `percent` for error ratios and utilization, `s` or `ms` for latency/duration, `bytes` or `Bps` for memory and throughput) — never leave `unit` unset or left at generic `"short"` on rates, ratios, durations, or byte counts
- Show data at appropriate granularity for the time range
- Use appropriate aggregation functions (`p50`/`p95`/`p99` for latency, ratios for errors, `sum(rate(...))` for throughput)
- Include sparklines in stat panels to show trends at a glance

---

## Visual Hierarchy and Accessibility

Guide viewers to important information through strategic design:

### Alignment

Follow natural reading patterns:

- In English-speaking contexts: left-to-right, top-to-bottom
- Place key metrics and KPIs in the upper-left area
- Group related metrics together

### Size

"The bigger the size of the component, the greater the perception of importance"

- Critical metrics should be larger and more prominent
- Supporting details can be smaller
- Use the full width of the dashboard for important visualizations

### Shape and Layout

- Complex shapes help elements stand out
- Use consistent panel sizes for related metrics
- Create visual separation between different sections
- Consider using rows to group related panels

### Accessibility

- Avoid red-green color combinations (colorblind users)
- Provide adequate contrast between text and background
- Use clear, readable fonts
- Include descriptive labels and units

---

## Panel Selection and Visualization Types

Choose the right visualization for your data type:

### Time Series Panels

**Best for:**

- Displaying temporal trends, patterns, and anomalies
- Metrics like latency, request rates, resource utilization
- Large numbers of time-based data points
- Identifying patterns over time

**Features:**

- X-axis shows time progression
- Y-axis shows metric magnitude
- Supports multiple series on one graph
- Ideal for correlation analysis

### Stat Panels

**Best for:**

- Displaying single values of interest (latest/current value)
- Monitoring key metrics at a glance (application health, bug counts, sales totals)
- Displaying aggregated data (average response time)
- Highlighting values outside normal thresholds

**Features:**

- Shows one large stat value
- Optional sparkline graph for trend context
- Background or value color based on thresholds
- Supports multiple values in compact format

### Gauge Panels

**Best for:**

- Presenting values relative to min/max ranges
- Visualizing progress toward a goal
- Comparing multiple values simultaneously
- Resource utilization (CPU, memory, disk)

**Types:**

- Standard radial gauge (single value)
- Horizontal/vertical bar gauge (multiple series)
- Three display modes for different use cases

### Bar Gauge Panels

Useful for:

- Comparing multiple values
- Progress visualization
- Displaying multiple series compactly (unlike standard gauge)

### Heatmap Panels

Best for:

- Visualizing latency or size **distributions over time** from histogram buckets
- Surfacing bimodal behavior, shifting modes, and tail outliers that single summary lines hide
- Pairing with p50/p95/p99 time series on RED Duration rows

### Pie Charts (Use Sparingly)

- Reserve pie charts strictly for static part-to-whole categorical breakdowns that sum to 100% at a single snapshot
- **Never** use a pie chart for temporal data, latency, percentiles, or request/error rates — use a **time series** or **heatmap** for latency and rates over time

---

## Organization and Navigation

### Template Variables

**Use template variables to:**

- Eliminate dashboard duplication across environments, clusters, services, and nodes
- Parameterize data sources (`type: "datasource"`, referenced as `${datasource}`) instead of hardcoding instance-specific datasource UIDs in panels, which break when provisioned into other Grafana instances
- Enable filtering by `environment`, `cluster`, `namespace`, `service`, and `instance`
- Create reusable master dashboards across environments

**Benefits:**

- Prevents dashboard sprawl
- Easier maintenance
- Consistent user experience
- Reduces storage and performance overhead

### Hierarchical Dashboard Structure

Implement drill-down capabilities:

1. **Top-level dashboards**: High-level overview of system health
2. **Service-level dashboards**: Specific service metrics and RED/USE methods
3. **Detailed dashboards**: Deep-dive into specific components or troubleshooting

**Navigation techniques:**

- Dashboard links in panels (drill-through on click)
- Panel links to related dashboards
- Dashboard list visualizations for easy navigation
- Text panels with markdown navigation menus
- URL parameters for customized views without duplication

### Cross-References and Linking

Create connections between related dashboards:

- Link from overview panels to detailed views
- Include "back" navigation to parent dashboards
- Use consistent URL parameters across dashboard hierarchy
- Add breadcrumb-style navigation in text panels

---

## Management and Maintenance

### Prevent Dashboard Sprawl

Dashboard sprawl is a common problem that reduces dashboard effectiveness:

**Prevention strategies:**

- **Regular audits**: Review and remove irrelevant or outdated dashboards
- **Prohibit casual copying**: Link to master dashboards with URL parameters instead
- **Track usage**: Use Grafana Enterprise features to identify unused dashboards
- **Clean up experiments**: Remove TEST/TMP dashboards when finished
- **Enforce naming conventions**: Make it easy to identify ownership and purpose

### Version Control

**Best practices:**

- Store dashboard JSON in version control (Git)
- Don't rely solely on Grafana's built-in versioning
- Use infrastructure-as-code approaches
- Enable code review for dashboard changes
- Tag releases to match application versions

### Dashboard Testing

- **Experiment in separate instances**: Use dev/staging Grafana instances
- **Validate with real data**: Test with production-like data volumes
- **Review with stakeholders**: Get feedback before promoting to production
- **Test across time ranges**: Ensure dashboards work with different time windows
- **Verify performance**: Check query execution times

### Consistency Through Automation

Use scripting libraries for standardized dashboards:

- **Grafonnet**: Jsonnet library for generating Grafana dashboards
- **Grafanalib**: Python library for building Grafana dashboards
- **Terraform/Pulumi**: Infrastructure-as-code for Grafana resources

**Benefits:**

- Ensures consistent patterns and styles
- Easier to maintain and update
- Version controlled dashboard definitions
- Reduces human error
- Enables automated dashboard generation

---

## Performance Optimization

### Refresh Rates

- Match auto-refresh intervals to both data scrape frequency and the dashboard's default time range
- Reserve sub-minute auto-refresh (`5s`–`15s`) for live incident views over short windows (`15m`–`1h`); pairing a fast refresh (such as `5s`) with a multi-day or multi-month window (`7d`, `30d`, `90d`) creates a severe **query-cost problem** by re-scanning massive history every few seconds
- Default operational dashboards to modest windows (`1h`–`24h`) with `30s`–`5m` refresh, and use manual refresh (`""`) for long-range historical analysis

### Query Optimization

- **Bound label cardinality**: Never group (`by (...)`) overview panels by unbounded or high-churn labels (user, customer, session, or request IDs, raw URL paths) or by per-instance/per-pod labels across a large fleet; aggregate by bounded dimensions (`service`, `route`, `status`) and filter individual instances behind template variables or drill-down views
- **Wrap counters and histograms in `rate()` with an interval**: Counter and `*_bucket` series are cumulative, so `histogram_quantile` must wrap `sum by (le) (rate(<metric>_bucket[$__rate_interval]))` — running `histogram_quantile` on raw bucket counters without `rate()` and a range interval produces meaningless all-time quantiles
- Use `$__rate_interval` rather than hardcoded windows so rate queries adapt cleanly to scrape intervals and zoom levels
- Leverage recording rules for expensive high-fanout or long-range aggregations

### Dashboard Complexity

- Limit number of panels per dashboard (aim for 20-30 max)
- Split complex dashboards into multiple focused dashboards
- Use shared queries when multiple panels need the same data
- Consider performance impact of transformations

---

## Maturity Model

Organizations typically evolve through these stages:

### Low Maturity: Dashboard Sprawl

- Uncontrolled, ad-hoc dashboard creation and casual UI cloning (titles ending in `copy`, `v2`, or environment suffixes)
- Duplicated dashboards per environment, cluster, or instance instead of parameterized views
- Absent naming conventions, folder structure, and ownership metadata
- Difficult to find or trust relevant dashboards during incidents, with high maintenance drift across copies

### Medium Maturity: Methodical Approach

- Adoption of a standard observability methodology (**RED**, **USE**, or **Four Golden Signals**) across service and resource dashboards
- Enforced **naming conventions**, folder hierarchy, and ownership tags
- **Template variables** (`environment`, `datasource`, `cluster`, `service`) collapsing per-environment and per-instance duplicates into single reusable dashboards
- Hierarchical organization (overview → service → detail) with drill-down links and documented dashboard purposes
- **Regular cleanup** and scheduled lifecycle audits to retire unused, outdated, or `TEST`/`TMP` dashboards

### High Maturity: Optimized Ecosystem

- Scripted dashboard generation (infrastructure-as-code with Grafonnet, Grafanalib, or Terraform)
- Comprehensive version control and peer review in Git
- Automated linting, testing, and schema validation in CI
- Deliberate curation, governance, and observability-as-code practices across all teams

### Advancing from Low to Medium Maturity

When an organization is in **Low maturity** (hundreds of dashboards, per-environment copies, no naming standard), do **not** jump straight to High-maturity code generation — scripting inconsistent copies only cements dashboard sprawl. Move to **Medium maturity** first through four coordinated steps:

1. **Collapse duplicates with template variables**: Parameterize `environment`, `datasource`, `cluster`, and `service` so per-environment and per-instance copies merge into one master dashboard per service or resource, and share filtered views via URL parameters (`?var-environment=prod`) instead of cloning.
2. **Establish a naming convention**: Adopt and enforce a consistent title and folder scheme (such as `<Team> / <Service> — <Methodology or Purpose>`), ownership tags, and `TEST`/`TMP` prefixes as dashboards are consolidated.
3. **Adopt RED, USE, or the Four Golden Signals**: Standardize service dashboards around **RED** or **Four Golden Signals** and resource dashboards around **USE**, with purpose text panels and overview-to-detail drill-down links.
4. **Institute regular cleanup**: Audit dashboard views/access logs on a recurring cadence, archive or delete dead and experimental dashboards, and prohibit casual UI copying.

Once Medium-maturity conventions are stable, advance to **High maturity** by managing dashboard definitions in Git and generating shared patterns as code.

### Continuous Improvement

Observability requires ongoing iteration:

- Regularly reassess metrics based on evolving needs
- Optimize layouts based on user feedback
- Update methodologies as systems evolve
- Remove dashboards that no longer serve a purpose
- Stay current with Grafana features and best practices

---

## Dashboard Review and Pre-Provisioning Audit

When auditing an existing dashboard JSON or reviewing a dashboard before provisioning, check both structural hygiene and query/visualization correctness:

- [ ] **Descriptive titles, no sprawl artifacts**: Dashboard and panel titles state what is measured; untouched defaults (`New dashboard`, `Panel Title`) and clone suffixes (`copy`, `v2`, `backup`, `- old`, per-env copies) are flagged as non-descriptive and as symptoms of **dashboard sprawl**
- [ ] **Templated datasources and dimensions**: `templating.list` defines a `datasource` variable (instead of hardcoded instance-specific datasource UIDs in panels) plus `environment`/`service`/`cluster` variables to avoid duplication
- [ ] **Methodology alignment**: Request-driven services follow **RED** or **Four Golden Signals** (rate, error ratio, latency percentiles/heatmap); infrastructure resources follow **USE**
- [ ] **Bounded query cardinality and valid PromQL**: `by (...)` clauses avoid unbounded labels (user/request IDs) and fleet-wide `instance`/`pod` fanout; `histogram_quantile` wraps `sum by (le) (rate(..._bucket[$__rate_interval]))` rather than raw counters without a `rate()` and interval
- [ ] **Matching visualization types**: Latency and rates over time use **time series** or **heatmap** panels, never **pie charts**
- [ ] **Explicit semantic units**: Every numeric panel sets a meaningful `unit` (`reqps`, `s`/`ms`, `percentunit`, `bytes`) — flag missing units and generic `"short"` units on rates, ratios, or durations
- [ ] **Refresh vs. time range cost**: Auto-refresh matches the default time window — flag fast refresh intervals (`5s`–`15s`) paired with multi-day or multi-month ranges (`30d`, `90d`)
- [ ] **Accessibility, documentation, and links**: Purpose text panel, panel descriptions, runbook/drill-down links, explicit `gridPos`, and colorblind-safe thresholds are in place

---

## Sources

- [Grafana dashboard best practices | Grafana documentation](https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/best-practices/)
- [Getting started with Grafana: best practices to design your first dashboard | Grafana Labs](https://grafana.com/blog/2024/07/03/getting-started-with-grafana-best-practices-to-design-your-first-dashboard/)
- [Best practices for Grafana dashboards | GrafanaCON 2025](https://grafana.com/events/observabilitycon/2025/hands-on-labs/best-practices-to-level-up-your-grafana-dashboarding-skills/)
- [Best practices for dashboards - Amazon Managed Grafana](https://docs.aws.amazon.com/grafana/latest/userguide/v10-dash-bestpractices.html)
- [Dashboarding Best Practices - Grafana Learning Platform](https://learn.grafana.com/dashboarding-best-practices)
- [Grafana Observability Dashboards: Insight & Best Practices](https://www.groundcover.com/learn/observability/grafana-dashboards)
- [Visualizations | Grafana documentation](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/)
