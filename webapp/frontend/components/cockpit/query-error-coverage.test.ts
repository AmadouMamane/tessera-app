import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const root = process.cwd();
const overviewScreens = [
  "components/access/access-overview.tsx",
  "components/automations/automations-overview.tsx",
  "components/connectors/connectors-overview.tsx",
  "components/curation/curation-overview.tsx",
  "components/inbox/inbox-overview.tsx",
  "components/incidents/incidents-overview.tsx",
  "components/integrations/integrations-overview.tsx",
  "components/parameters/parameters-overview.tsx",
  "components/policies/policies-overview.tsx",
  "components/proofs/proofs-overview.tsx",
  "components/replay/replay-overview.tsx",
  "components/signals/signal-catalogue.tsx",
  "components/sources/sources-overview.tsx",
  "components/system/system-profile.tsx",
  "components/users/users-overview.tsx",
] as const;

describe("overview query errors", () => {
  it.each(overviewScreens)("renders a recoverable unavailable state in %s", (file) => {
    const source = readFileSync(join(root, file), "utf8");
    expect(source).toContain('from "@/components/cockpit/query-error-state"');
    expect(source).toContain("isError");
    expect(source).toContain("<QueryErrorState");
    expect(source).toContain("refetch()");
  });
});
