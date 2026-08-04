// @vitest-environment jsdom

import { act, fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";

import { DetailDrawer } from "./detail-drawer";

function renderDrawer(onClose = vi.fn()) {
  return render(
    <NextIntlClientProvider locale="fr" messages={{ table: { close: "Fermer" } }}>
      <TooltipProvider>
        <main style={{ position: "fixed", inset: "88px 24px 64px 96px" }}>
          <div data-shell-content style={{ width: 800 }} />
        </main>
        <DetailDrawer title="Détail" onClose={onClose} testId="drawer-body">
          Contenu
        </DetailDrawer>
      </TooltipProvider>
    </NextIntlClientProvider>,
  );
}

describe("DetailDrawer", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("uses the full viewport on phones instead of inheriting the narrow content frame", () => {
    vi.stubGlobal("innerWidth", 390);

    renderDrawer();

    const overlay = screen.getByRole("dialog").parentElement;
    expect(overlay?.getAttribute("style")).toContain("inset: 0");
  });

  it("closes with Escape and restores the opener focus", async () => {
    vi.stubGlobal("innerWidth", 390);
    const onClose = vi.fn();
    const opener = document.createElement("button");
    document.body.append(opener);
    opener.focus();

    const view = renderDrawer(onClose);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();

    view.unmount();
    await act(async () => undefined);
    expect(document.activeElement).toBe(opener);
    opener.remove();
  });
});
