import { useMemo, useState } from "react";

import {
  evidenceIndex,
  getTrace,
  ocrExtract,
  replay,
  underwrite,
  type TraceNode,
  type UnderwritePayload,
  type UnderwriteResponse,
} from "./api/client";

const DEFAULT_PAYLOAD: UnderwritePayload = {
  credit_score: 710,
  monthly_income: 9000,
  monthly_debt: 2600,
  loan_amount: 280000,
  property_value: 450000,
  occupancy: "primary",
};

const DEFAULT_TEXT =
  "Stable payroll and employment records support income verification.";

export function App() {
  const [caseId, setCaseId] = useState("demo_case_001");
  const [filename, setFilename] = useState("demo_note.txt");
  const [documentText, setDocumentText] = useState(DEFAULT_TEXT);
  const [documentId, setDocumentId] = useState("");
  const [payloadText, setPayloadText] = useState(
    JSON.stringify(DEFAULT_PAYLOAD, null, 2),
  );
  const [modelVersion, setModelVersion] = useState("baseline_v1");
  const [topK, setTopK] = useState(5);

  const [underwriteResult, setUnderwriteResult] =
    useState<UnderwriteResponse | null>(null);
  const [replayResult, setReplayResult] = useState<UnderwriteResponse | null>(null);
  const [traceTimeline, setTraceTimeline] = useState<TraceNode[]>([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [isBusy, setIsBusy] = useState(false);

  const replayComparison = useMemo(() => {
    if (!underwriteResult || !replayResult) {
      return null;
    }

    const underwriteChunks = underwriteResult.justification.citations.map(
      (item) => item.chunk_id,
    );
    const replayChunks = replayResult.justification.citations.map(
      (item) => item.chunk_id,
    );

    const pass =
      underwriteResult.decision === replayResult.decision &&
      Number(underwriteResult.risk_score) === Number(replayResult.risk_score) &&
      JSON.stringify(underwriteChunks) === JSON.stringify(replayChunks);

    return {
      pass,
      message: pass
        ? "Replay comparison passed (decision, risk_score, citations)."
        : "Replay mismatch detected.",
    };
  }, [replayResult, underwriteResult]);

  async function runAction(action: () => Promise<void>) {
    setError("");
    setStatus("");
    setIsBusy(true);
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsBusy(false);
    }
  }

  function parsePayload(): UnderwritePayload {
    const parsed = JSON.parse(payloadText) as UnderwritePayload;
    return parsed;
  }

  return (
    <div className="app">
      <section className="panel">
        <h1>Mortgage Demo Inputs</h1>

        <label>
          Case ID
          <input value={caseId} onChange={(e) => setCaseId(e.target.value)} />
        </label>

        <label>
          Filename
          <input value={filename} onChange={(e) => setFilename(e.target.value)} />
        </label>

        <label>
          Paste document text
          <textarea
            value={documentText}
            onChange={(e) => setDocumentText(e.target.value)}
          />
        </label>

        <label>
          Or upload a text file
          <input
            type="file"
            accept=".txt,text/plain"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (!file) {
                return;
              }
              setFilename(file.name);
              setDocumentText(await file.text());
            }}
          />
        </label>

        <button
          disabled={isBusy}
          onClick={() =>
            runAction(async () => {
              const content_b64 = btoa(unescape(encodeURIComponent(documentText)));
              const response = await ocrExtract(
                caseId,
                filename,
                "text/plain",
                content_b64,
              );
              setDocumentId(response.document_id);
              setStatus(`OCR extracted: document_id=${response.document_id}`);
            })
          }
        >
          OCR Extract
        </button>

        <button
          disabled={isBusy || !documentId}
          onClick={() =>
            runAction(async () => {
              await evidenceIndex(caseId, documentId, true);
              setStatus("Evidence indexed.");
            })
          }
        >
          Index Evidence
        </button>

        <div className="status">Current document_id: {documentId || "(none)"}</div>

        <h2>Underwrite request payload</h2>
        <textarea
          value={payloadText}
          onChange={(e) => setPayloadText(e.target.value)}
        />

        <label>
          model_version
          <input
            value={modelVersion}
            onChange={(e) => setModelVersion(e.target.value)}
          />
        </label>

        <label>
          top_k
          <input
            type="number"
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value || 1))}
            min={1}
          />
        </label>

        <button
          disabled={isBusy}
          onClick={() =>
            runAction(async () => {
              const payload = parsePayload();
              const result = await underwrite(caseId, payload, modelVersion, topK);
              setUnderwriteResult(result);
              setReplayResult(null);
              const trace = await getTrace(caseId, result.request_id);
              setTraceTimeline(trace);
              setStatus(`Underwrite complete. request_id=${result.request_id}`);
            })
          }
        >
          Underwrite
        </button>

        {error ? <div className="error">{error}</div> : null}
        {status ? <div className="status">{status}</div> : null}
      </section>

      <section className="panel">
        <h1>Results</h1>
        {!underwriteResult ? (
          <p>Run underwrite to view decision, citations, trace, and replay.</p>
        ) : (
          <>
            <div className="status">
              <strong>Decision:</strong> {underwriteResult.decision} &nbsp;|&nbsp;
              <strong>Risk score:</strong> {underwriteResult.risk_score}
            </div>

            <h2>Reasons</h2>
            <ul>
              {underwriteResult.justification.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>

            <h2>Justification summary</h2>
            <p>{underwriteResult.justification.summary}</p>

            <h2>Citations</h2>
            <table>
              <thead>
                <tr>
                  <th>document_id</th>
                  <th>chunk_id</th>
                  <th>score</th>
                  <th>start_char</th>
                  <th>end_char</th>
                </tr>
              </thead>
              <tbody>
                {underwriteResult.justification.citations.map((item) => (
                  <tr key={`${item.document_id}:${item.chunk_id}`}>
                    <td>{item.document_id}</td>
                    <td>{item.chunk_id}</td>
                    <td>{item.score}</td>
                    <td>{item.start_char}</td>
                    <td>{item.end_char}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <h2>Trace timeline</h2>
            <table>
              <thead>
                <tr>
                  <th>node_name</th>
                  <th>duration_ms</th>
                </tr>
              </thead>
              <tbody>
                {traceTimeline.map((node, idx) => (
                  <tr key={`${node.node_name}-${idx}`}>
                    <td>{node.node_name}</td>
                    <td>{node.duration_ms}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <button
              disabled={isBusy}
              onClick={() =>
                runAction(async () => {
                  const replayResponse = await replay(
                    caseId,
                    underwriteResult.request_id,
                  );
                  setReplayResult(replayResponse);
                  setStatus("Replay completed.");
                })
              }
            >
              Replay
            </button>

            {replayComparison ? (
              <div
                className={replayComparison.pass ? "banner-pass" : "banner-fail"}
              >
                {replayComparison.message}
              </div>
            ) : null}
          </>
        )}
      </section>
    </div>
  );
}
