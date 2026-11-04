import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Markdown } from "./markdown";

describe("Markdown", () => {
  it("renders headings, bullets, bold, code and italic", () => {
    render(<Markdown source={"# Title\n\n_Note with list_turbines inside._\n\n## Part\n- one **bold**\n- two `code`"} />);
    expect(screen.getByRole("heading", { level: 2, name: "Title" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: "Part" })).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByText("bold").tagName).toBe("STRONG");
    expect(screen.getByText("code").tagName).toBe("CODE");
    expect(screen.getByText(/Note with list_turbines inside\./).tagName).toBe("EM");
  });

  it("never injects markup from model text", () => {
    const { container } = render(<Markdown source={'<img src=x onerror="alert(1)"> <script>boom</script>'} />);
    expect(container.querySelector("img, script")).toBeNull();
    expect(container.textContent).toContain("<script>boom</script>");
  });
});
