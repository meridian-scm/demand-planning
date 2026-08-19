import type { Insight } from "@/types/api";

interface InsightPanelProps {
  insight: Insight | undefined;
  onGenerate: () => void;
  isGenerating: boolean;
}

/** Human-readable label for how a narrative was produced, from the backend's
 * `generated_by` + `model_name` fields — never hardcoded to one provider, so
 * this stays accurate whether the API is configured for Ollama, Groq, or the
 * deterministic template fallback. */
function provenanceLabel(insight: Insight): string {
  if (insight.generated_by === "template") return "template summary";
  return insight.model_name ? `${insight.model_name} via ${insight.generated_by}` : insight.generated_by;
}

/** Renders an AI narrative, honestly labelled with its provenance. */
export function InsightPanel({ insight, onGenerate, isGenerating }: InsightPanelProps) {
  return (
    <div className="ai-panel">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
        <span className="ai-panel-tag">
          ✨ AI Insight{" "}
          {insight && (
            <span style={{ color: "var(--color-text-faint)", fontWeight: 500, textTransform: "none" }}>
              · {provenanceLabel(insight)}
            </span>
          )}
        </span>
        <button className="btn btn-sm" onClick={onGenerate} disabled={isGenerating}>
          {isGenerating ? "Generating…" : insight ? "Regenerate" : "Generate"}
        </button>
      </div>

      {!insight && !isGenerating && (
        <p style={{ margin: 0, color: "var(--color-text-muted)", fontSize: 13 }}>
          Generate an AI-written summary of the current demand planning position.
        </p>
      )}

      {insight && (
        <>
          <h3 style={{ margin: "4px 0 6px", fontSize: 15 }}>{insight.headline}</h3>
          <p style={{ margin: 0, color: "var(--color-text-muted)", fontSize: 13.5 }}>{insight.summary}</p>
          {insight.recommendations && insight.recommendations.length > 0 && (
            <ul className="recommendation-list">
              {insight.recommendations.map((rec, index) => (
                <li key={index}>{rec}</li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
