/**
 * @deprecated Transitional shim (ADR 0017 Phase A). The panel is now the generic
 * `WorkflowRunsPanel` — agent-specific copy comes in through props at the call site.
 * This re-export dies with the hardcoded `recouvrement` tab in Phase C (step 4).
 */
export { WorkflowRunsPanel as RecouvrementRunsPanel } from "./workflow-runs-panel";
