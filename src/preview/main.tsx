import React from "react";
import { createRoot } from "react-dom/client";

function Preview(): React.JSX.Element {
  return <main data-testid="preview-root">DeepSeek Character UI</main>;
}

const rootElement = document.getElementById("root");

if (rootElement) {
  createRoot(rootElement).render(<Preview />);
}
