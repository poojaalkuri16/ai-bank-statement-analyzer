import React, { useCallback, useRef, useState } from 'react'
import { uploadStatement } from './api'

const SUGGESTIONS = [
  'How much did I spend this month?',
  'What is my account balance?',
  'Show my largest expense.',
  'Where is my money going?',
  'Top merchants?',
  'Show Food transactions.',
]

/**
 * UploadView
 * ----------
 * Shown on first load and when the user clicks "New Statement".
 */
export default function UploadView({ onSessionReady }) {
  const [phase, setPhase]         = useState('idle')    // idle | uploading | done | error
  const [dragOver, setDragOver]   = useState(false)
  const [errorMsg, setErrorMsg]   = useState('')
  const [summary, setSummary]     = useState(null)
  const [sessionId, setSessionId] = useState(null)
  const fileInputRef              = useRef(null)

  const handleFile = useCallback(async (file) => {
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setErrorMsg('Only PDF files are supported. Please select a valid PDF bank statement.')
      setPhase('error')
      return
    }

    setPhase('uploading')
    setErrorMsg('')
    setSummary(null)

    try {
      const data = await uploadStatement(file)
      setSummary(data.summary)
      setSessionId(data.session_id)
      setPhase('done')

      // Wait 1.8 s so the user can read the summary, then enter chat
      setTimeout(() => {
        onSessionReady({
          sessionId:   data.session_id,
          summary:     data.summary,
          suggestions: SUGGESTIONS,
        })
      }, 1800)
    } catch (err) {
      setErrorMsg(err.message || 'An unexpected error occurred while parsing the statement.')
      setPhase('error')
    }
  }, [onSessionReady])

  // ── Drag-and-drop ──────────────────────────────────────────────────────
  const onDragOver  = (e) => { e.preventDefault(); setDragOver(true)  }
  const onDragLeave = ()  => { setDragOver(false) }
  const onDrop      = (e) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleFile(file)
  }
  const onInputChange = (e) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
    e.target.value = ''   // allow re-selecting the same file
  }

  return (
    <div className="upload-view glass-panel animate-slide-up">
      <div className="upload-logo">💰</div>
      <h1>Finance AI Agent</h1>
      <p className="subtitle">Upload your bank statement PDF to extract insights and ask questions about your finances in plain English.</p>

      {/* ── Uploading Phase ── */}
      {phase === 'uploading' && (
        <div className="loading-overlay">
          <div className="spinner-container">
            <div className="spinner-glow" />
            <div className="spinner" />
          </div>
          <h2>Analyzing your statement…</h2>
          <p>
            This can take up to a few minutes on first use as the local Ollama AI model starts up.
            Please do not close this window.
          </p>
        </div>
      )}

      {/* ── Success summary ── */}
      {phase === 'done' && summary && (
        <div className="summary-card">
          <h3>Statement parsed successfully</h3>
          <div className="summary-grid">
            <div className="summary-item">
              <span className="label">Bank Name</span>
              <span className="value">{summary.bank_name}</span>
            </div>
            <div className="summary-item">
              <span className="label">Transactions</span>
              <span className="value">{summary.transaction_count}</span>
            </div>
            <div className="summary-item">
              <span className="label">Confidence</span>
              <span className="value">{summary.extraction_confidence}%</span>
            </div>
            {summary.statement_name && (
              <div className="summary-item">
                <span className="label">Statement Type</span>
                <span className="value">{summary.statement_name}</span>
              </div>
            )}
            {summary.statement_start_date && (
              <div className="summary-item full-width">
                <span className="label">Period Range</span>
                <span className="value">
                  {summary.statement_start_date} — {summary.statement_end_date}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Dropzone (shown in idle and error states) ── */}
      {(phase === 'idle' || phase === 'error') && (
        <>
          <div
            className={`dropzone${dragOver ? ' drag-over' : ''}`}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
            onClick={() => fileInputRef.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && fileInputRef.current?.click()}
            aria-label="Drop a PDF here or click to select"
          >
            <div className="dropzone-icon">
              {/* Document upload icon */}
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="12" y1="18" x2="12" y2="12" />
                <polyline points="9 15 12 12 15 15" />
              </svg>
            </div>
            <div className="dropzone-label">Drop your PDF here or click to select</div>
            <div className="dropzone-hint">Supports popular layouts (SBI, ICICI, Union Bank, etc.)</div>
            <button
              className="btn btn-primary"
              onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click() }}
            >
              Choose PDF
            </button>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            style={{ display: 'none' }}
            onChange={onInputChange}
          />
        </>
      )}

      {/* ── Error ── */}
      {phase === 'error' && errorMsg && (
        <div className="error-box">{errorMsg}</div>
      )}
    </div>
  )
}
