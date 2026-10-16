/* Use case: Defines exact wire contracts for private anomaly and allocation views.
What it does: Keeps numerical results as returned strings and labels conditional decisions. */
export type AnalysisOptions = {
    state: string;
    revision_id: string;
    understanding_id: string;
    metrics: {
        name: string;
        unit: string;
    }[];
    entities: string[];
};
export type AnalysisSummary = {
    id: string;
    name: string;
    kind: string;
    created_at: string;
};
export type Finding = {
    id: string;
    value: string;
    count: number;
    absolute_difference: string;
    score: string | null;
    segment?: string;
};
export type AnomalyResult = {
    baseline: string | null;
    covered_records?: number;
    excluded_records?: number;
    groups?: { segment: string | null; status: string; sample_count: number; missing_records: number; baseline?: string; }[];
    sample_count: number;
    method: string;
    threshold: string;
    materiality: string;
    flagged_records: number;
    findings: Finding[];
    limitations: string[];
};
export type AllocationResult = {
    status: string;
    budget: string;
    quantum: string;
    cost: string | null;
    benefit: string | null;
    unused_budget?: string;
    resource_capacity?: string;
    resource_used?: string | null;
    unused_resource?: string | null;
    reason?: string;
    solver_status?: "optimal" | "infeasible";
    selection_rules?: {
        prerequisites: { candidate: string; requires: string }[];
        exclusions: { first: string; second: string }[];
    };
    verification?: { quantities: string; resources: string; selection_rules: string };
    baseline: {
        cost: string;
        benefit: string;
        feasible: boolean;
    };
    allocations: {
        candidate: string;
        quantity: number;
        unit_cost: string;
        unit_benefit: string;
        cost: string;
        benefit: string;
        minimum: number;
        maximum: number;
        resource?: string;
    }[];
    assumptions: string[];
    limitations: string[];
};
export type AnalysisBody = {
    run: AnalysisSummary & {
        method_version: string;
        result: AnomalyResult | AllocationResult;
        evidence: {
            query_id: string;
            units: Record<string, string>;
            sources: {
                upload_id: string;
                revision_id: string;
                source_checksum: string;
                understanding_id: string;
            }[];
            result_checksum: string;
        };
    };
    current: boolean;
    review_version: number;
    decision_status: string;
    approval_effective: boolean;
    reviews: {
        id: string;
        sequence: number;
        target: string;
        status: string;
        note: string;
        created_at: string;
    }[];
};
