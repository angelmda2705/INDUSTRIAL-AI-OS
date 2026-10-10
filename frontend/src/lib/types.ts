export type Me = {
  user: { id: number; email: string; display_name: string; is_platform_admin: boolean; must_change_password: boolean };
  organization: {
    id: number;
    name: string;
    slug: string;
    plan_code: string | null;
    plan_name: string | null;
    modules: string[];
    limits: Record<string, number>;
    settings: Record<string, unknown>;
  } | null;
  role: string | null;
  role_label: string | null;
  permissions: string[];
  memberships: { organization_id: number; organization_name: string; role: string; role_label: string }[];
  session_expires_at: string | null;
};

export type Page<T> = { items: T[]; total: number; page: number; page_size: number };

export type ImportJob = {
  id: number;
  original_filename: string;
  file_type: string;
  file_size: number;
  file_sha256: string;
  status: "parsed" | "validated" | "committed" | "reverted" | "failed";
  sheet_names: string[];
  sheet_name: string | null;
  detected_columns: string[];
  total_rows: number;
  template_code: string | null;
  column_mapping: Record<string, string>;
  parse_options: Record<string, string | null>;
  target_dataset_id: number | null;
  target_dataset_name: string | null;
  validation_summary: ValidationSummary | Record<string, never>;
  valid_rows: number;
  invalid_rows: number;
  duplicate_rows: number;
  imported_rows: number;
  created_at: string;
  committed_at: string | null;
  reverted_at: string | null;
  is_demo: boolean;
};

export type RowError = { row: number; field: string; field_label: string; column: string | null; value: unknown; message: string };

export type ValidationSummary = {
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  duplicate_rows: number;
  duplicates_in_file: { row: number; duplicate_of_row: number }[];
  duplicates_existing_rows: number[];
  importable_rows_without_duplicates: number;
  errors: RowError[];
  errors_truncated: boolean;
  missing_by_field: Record<string, number>;
  duplicate_basis: string[];
  unmapped_columns: string[];
  commit?: { imported_rows: number; skipped_invalid_rows: number; skipped_duplicate_rows: number };
};

export type Preview = {
  columns: { name: string; kind: string; missing: number; examples: string[] }[];
  rows: { row: number; values: unknown[] }[];
  total_rows: number;
  sheet_names: string[];
  sheet_name: string | null;
  suggested_mappings: Record<string, Record<string, string>>;
  same_file_committed_import_ids: number[];
};

export type TemplateField = {
  name: string;
  label: string;
  type: string;
  required: boolean;
  description: string;
  choices: string[];
};

export type Template = {
  code: string;
  name: string;
  area: string;
  description: string;
  generic: boolean;
  key_fields: string[];
  fields: TemplateField[];
  kpis: string[];
};

export type Dataset = {
  id: number;
  name: string;
  description: string | null;
  template_code: string;
  is_demo: boolean;
  row_count: number;
  created_at: string;
  last_analyzed_at: string | null;
  analysis_stale: boolean;
};

export type AnalysisRun = {
  id: number;
  dataset_id: number;
  trigger: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  record_count: number;
  period_start: string | null;
  period_end: string | null;
  summary: Record<string, number>;
  error_message: string | null;
};

export type FieldProfile = {
  field: string;
  label: string;
  type: string;
  missing: number;
  missing_pct: number | null;
  distinct: number;
  min?: number | string | null;
  max?: number | string | null;
  mean?: number | null;
  median?: number | null;
  std?: number | null;
  negatives?: number;
  iqr_outliers?: number;
  top_values?: { value: string; count: number }[];
};

export type DataProfile = {
  row_count: number;
  completeness_pct: number | null;
  completeness_definition: string;
  date_range: { from: string; to: string } | null;
  fields: FieldProfile[];
};

export type KpiDefinition = {
  code: string;
  name: string;
  area: string;
  template: string;
  description: string;
  formula: string;
  unit: string;
  frequency: string;
  required_fields: string[];
  min_requirements: string;
  missing_handling: string;
  assumptions: string[];
  direction: "higher_is_better" | "lower_is_better" | "neutral";
  dimension: string | null;
  monthly: boolean;
  target: KpiTarget | null;
};

export type KpiTarget = { target_value: number; tolerance: number; owner_label: string | null; notes: string | null; updated_at: string };

export type KpiValue = {
  kpi_code: string;
  name: string;
  area: string;
  unit: string;
  direction: string;
  dataset_id: number;
  dataset_name: string;
  is_demo: boolean;
  analysis_run_id: number;
  computed_at: string;
  period_start: string | null;
  period_end: string | null;
  value: number | null;
  status: "ok" | "insufficient_data";
  sample_size: number;
  inputs: Record<string, unknown>;
  message: string | null;
  target: number | null;
  evaluation: "meets" | "misses" | null;
};

export type Finding = {
  id: number;
  code: string;
  dataset_id: number | null;
  area: string;
  category: string;
  nature: "statistical_anomaly" | "confirmed_issue" | "hypothesis";
  title: string;
  description: string;
  rule_code: string;
  method: string;
  priority: "critical" | "high" | "medium" | "low";
  impact_amount: number | null;
  impact_currency: string | null;
  impact_basis: string | null;
  impact_kind: "recorded_cost" | "estimated_excess_cost" | "capital_tied" | null;
  confidence: string | null;
  confidence_basis: string | null;
  recommendation: string;
  status: "open" | "in_review" | "action_planned" | "resolved" | "dismissed";
  owner_user_id: number | null;
  due_date: string | null;
  first_detected_at: string;
  last_detected_at: string;
  condition_active: boolean;
  last_analysis_run_id: number | null;
  is_demo: boolean;
};

export type FindingEvent = {
  id: number;
  actor_label: string;
  event_type: string;
  from_status: string | null;
  to_status: string | null;
  note: string | null;
  data: Record<string, unknown>;
  created_at: string;
};

export type FindingDetail = Finding & {
  evidence: Record<string, unknown>;
  events: FindingEvent[];
  dataset_name: string | null;
  owner_name: string | null;
};

export type Member = {
  id: number;
  user_id: number;
  email: string;
  display_name: string;
  role: string;
  role_label: string;
  is_active: boolean;
  last_login_at: string | null;
  must_change_password: boolean;
};

export type Report = {
  id: number;
  report_type: string;
  file_format: "pdf" | "xlsx";
  title: string;
  file_sha256: string;
  file_size: number;
  parameters: Record<string, unknown>;
  created_at: string;
};

export type AuditEntry = {
  id: number;
  actor_label: string;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  details: Record<string, unknown>;
  ip_address: string | null;
  request_id: string | null;
  created_at: string;
};

export type Dashboard = {
  has_data: boolean;
  has_demo_data: boolean;
  currency: string;
  datasets: (Pick<Dataset, "id" | "name" | "template_code" | "row_count" | "is_demo" | "last_analyzed_at" | "analysis_stale">)[];
  total_records: number;
  findings: {
    open_total: number;
    resolved_total: number;
    by_priority: Record<string, number>;
    by_area: Record<string, number>;
    by_nature: Record<string, number>;
    top: (Pick<Finding, "id" | "code" | "title" | "priority" | "area" | "nature" | "status" | "impact_amount" | "impact_currency" | "impact_kind" | "is_demo" | "condition_active">)[];
  };
  impact: { open_by_kind: Record<string, { amount: number; findings: number }>; note: string };
  kpis: KpiValue[];
  series: { kpi_code: string; name: string; unit: string; dataset_id: number; dataset_name: string; points: { period: string; value: number }[] }[];
  recent_imports: { id: number; filename: string; status: string; created_at: string; imported_rows: number; is_demo: boolean }[];
  activity: { id: number; action: string; actor: string; entity_type: string | null; entity_id: string | null; created_at: string }[];
};
