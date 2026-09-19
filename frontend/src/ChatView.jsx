import React, { useCallback, useEffect, useRef, useState } from 'react'
import { sendMessage } from './api'

/**
 * Format an ISO date string (YYYY-MM-DD) into "DD MMM YYYY"
 */
function formatDate(iso) {
  if (!iso) return '?'
  const [y, m, d] = iso.split('-')
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  return `${parseInt(d, 10)} ${months[parseInt(m, 10) - 1]} ${y}`
}

/**
 * Format a HH:MM time string from a Date object.
 */
function hhmm(date) {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

/**
 * Parse assistant response into structure nodes.
 * E.g., headers, paragraphs, and typed lists.
 */
function parseBotResponse(text) {
  if (!text) return []
  const lines = text.split('\n')
  const nodes = []
  let currentList = null

  const flushList = () => {
    if (currentList) {
      nodes.push(currentList)
      currentList = null
    }
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const trimmed = line.trim()

    if (trimmed === '') {
      continue
    }

    // Check for main section headers
    if (/^(Category-wise Spending Summary|Top Spending Merchants|Financial Summary|Largest Spending Category|Statement Summary)/i.test(trimmed)) {
      flushList()
      nodes.push({ type: 'header', text: trimmed })
      continue
    }

    // Check for list items like "1. ..."
    const listMarkerMatch = line.match(/^\s*(\d+)\.\s*(.*)$/)
    if (listMarkerMatch) {
      const index = listMarkerMatch[1]
      const rest = listMarkerMatch[2].trim()

      // Case A: Category Item (e.g. "1. Entertainment — ₹825.42" or "1. Shopping - ₹15,118.67")
      const categoryMatch = rest.match(/^(.+?)\s*(?:[\u2014\u2013-]|--)\s*(₹[\d,]+(?:\.\d{2})?)$/)
      if (categoryMatch) {
        if (!currentList || currentList.listType !== 'categories') {
          flushList()
          currentList = { type: 'list', listType: 'categories', items: [] }
        }
        currentList.items.push({
          index,
          label: categoryMatch[1].trim(),
          amount: categoryMatch[2].trim()
        })
        continue
      }

      // Case B: Transaction Item (e.g. "1. 10 Dec 2023  [DEBIT]")
      const txnHeaderMatch = rest.match(/^(\d{2}\s+[A-Za-z]{3}\s+\d{4})(?:\s+\[(DEBIT|CREDIT)\])?$/i)
      if (txnHeaderMatch) {
        let desc = ''
        let amount = ''
        let lookAheadCount = 0

        // Look ahead for description
        if (i + 1 < lines.length && lines[i + 1].trim() !== '' && !/^\s*\d+\.\s*/.test(lines[i + 1])) {
          desc = lines[i + 1].trim()
          lookAheadCount++
          // Look ahead for amount
          if (i + 2 < lines.length && lines[i + 2].trim() !== '' && !/^\s*\d+\.\s*/.test(lines[i + 2])) {
            amount = lines[i + 2].trim()
            lookAheadCount++
          }
        }

        if (desc && amount && amount.includes('₹')) {
          if (!currentList || currentList.listType !== 'transactions') {
            flushList()
            currentList = { type: 'list', listType: 'transactions', items: [] }
          }
          currentList.items.push({
            index,
            date: txnHeaderMatch[1].trim(),
            type: txnHeaderMatch[2] ? txnHeaderMatch[2].trim().toUpperCase() : '',
            desc,
            amount
          })
          i += lookAheadCount
          continue
        }
      }

      // Case C: Merchant Item (e.g. "1. FLIPKART" followed by a line with amount)
      if (i + 1 < lines.length && lines[i + 1].trim() !== '' && !/^\s*\d+\.\s*/.test(lines[i + 1])) {
        const nextLineTrimmed = lines[i + 1].trim()
        if (nextLineTrimmed.includes('₹')) {
          if (!currentList || currentList.listType !== 'merchants') {
            flushList()
            currentList = { type: 'list', listType: 'merchants', items: [] }
          }
          currentList.items.push({
            index,
            merchant: rest,
            amount: nextLineTrimmed
          })
          i += 1
          continue
        }
      }
    }

    // Default: paragraph note/text
    flushList()
    nodes.push({ type: 'paragraph', text: line })
  }

  flushList()
  return nodes
}

/**
 * Render parsed structured nodes in React.
 */
function renderParsedNode(node, idx) {
  if (node.type === 'header') {
    return <h3 key={idx} className="bot-response-header">{node.text}</h3>
  }

  if (node.type === 'paragraph') {
    const textLower = node.text.toLowerCase()
    const isNote = textLower.startsWith('note:') || textLower.startsWith('your top 3') || textLower.startsWith('...and')
    return (
      <p key={idx} className={`bot-response-paragraph ${isNote ? 'bot-response-note' : ''}`}>
        {node.text}
      </p>
    )
  }

  if (node.type === 'list') {
    if (node.listType === 'transactions') {
      return (
        <div key={idx} className="structured-list transactions-list">
          {node.items.map((item, itemIdx) => (
            <div key={itemIdx} className="structured-item transaction-item">
              <div className="item-row header-row">
                <span className="item-index">{item.index}.</span>
                <span className="item-date">{item.date}</span>
                {item.type && (
                  <span className={`item-badge ${item.type.toLowerCase()}`}>
                    {item.type}
                  </span>
                )}
              </div>
              <div className="item-row content-row">
                <span className="item-desc">{item.desc}</span>
                <span className="item-amount highlight">{item.amount}</span>
              </div>
            </div>
          ))}
        </div>
      )
    }

    if (node.listType === 'categories' || node.listType === 'merchants') {
      const isCat = node.listType === 'categories'
      return (
        <div key={idx} className={`structured-list ${node.listType}-list`}>
          {node.items.map((item, itemIdx) => (
            <div key={itemIdx} className="structured-item summary-item-row">
              <div className="item-row content-row">
                <div className="item-left">
                  <span className="item-index">{item.index}.</span>
                  <span className="item-desc">{isCat ? item.label : item.merchant}</span>
                </div>
                <span className="item-amount highlight">{item.amount}</span>
              </div>
            </div>
          ))}
        </div>
      )
    }
  }

  return null
}

/**
 * ChatView
 * --------
 * Full-height chat interface for an active session.
 */
export default function ChatView({ sessionId, summary, suggestions, onNewStatement }) {
  const [messages, setMessages] = useState([])       // { id, role, text, time }
  const [input, setInput]       = useState('')
  const [busy, setBusy]         = useState(false)
  const chatMessagesRef         = useRef(null)
  const inputRef                = useRef(null)

  const scrollToBottom = useCallback((behavior = 'smooth') => {
    if (chatMessagesRef.current) {
      chatMessagesRef.current.scrollTo({
        top: chatMessagesRef.current.scrollHeight,
        behavior
      })
    }
  }, [])

  // Scroll to bottom whenever messages change or typing state changes
  useEffect(() => {
    scrollToBottom('auto')
    const timer = setTimeout(() => scrollToBottom('smooth'), 60)
    return () => clearTimeout(timer)
  }, [messages, busy, scrollToBottom])

  const addMessage = (role, text) => {
    setMessages(prev => [
      ...prev,
      { id: Date.now() + Math.random(), role, text, time: new Date() },
    ])
  }

  const handleSend = useCallback(async (text) => {
    const q = (text || input).trim()
    if (!q || busy) return

    setInput('')
    addMessage('user', q)
    setBusy(true)

    try {
      const data = await sendMessage(sessionId, q)
      addMessage('bot', data.answer)
    } catch (err) {
      addMessage('bot', `⚠️ ${err.message || 'An error occurred. Please try again.'}`)
    } finally {
      setBusy(false)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [input, busy, sessionId])

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  // Auto-resize textarea
  const onInputChange = (e) => {
    setInput(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 120) + 'px'
  }

  // Header subtitle — bank name + period
  const subtitle = [
    summary?.bank_name,
    summary?.statement_start_date
      ? `${formatDate(summary.statement_start_date)} – ${formatDate(summary.statement_end_date)}`
      : null,
    summary?.transaction_count ? `${summary.transaction_count} txs` : null,
  ].filter(Boolean).join('  ·  ')

  return (
    <div className="chat-view glass-panel animate-slide-up">
      {/* ── Header ── */}
      <header className="chat-header">
        <div className="chat-header-left">
          <span className="chat-header-title">💰 Finance AI Agent</span>
          {subtitle && <span className="chat-header-sub">{subtitle}</span>}
        </div>
        <button
          className="btn btn-ghost"
          onClick={onNewStatement}
          title="Upload a new statement"
        >
          {/* Refresh/plus icon */}
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '6px' }}>
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          New Statement
        </button>
      </header>

      {/* ── Messages Thread ── */}
      <div ref={chatMessagesRef} className="chat-messages">
        {messages.length === 0 ? (
          /* Empty state with suggested questions */
          <div className="chat-empty">
            <div className="chat-empty-icon">🤔</div>
            <h2>Ask anything about your statement</h2>
            <p>Select a suggestion below or write a custom question to query details, summaries, or categories.</p>
            <div className="suggestions">
              {suggestions.map((s) => (
                <button
                  key={s}
                  className="suggestion-chip"
                  onClick={() => handleSend(s)}
                  disabled={busy}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id} className={`message ${msg.role}`}>
              <div className="bubble">
                {msg.role === 'bot' ? (
                  parseBotResponse(msg.text).map((node, idx) => renderParsedNode(node, idx))
                ) : (
                  msg.text
                )}
              </div>
              <span className="message-time">{hhmm(msg.time)}</span>
            </div>
          ))
        )}

        {/* Typing indicator */}
        {busy && (
          <div className="message bot">
            <div className="typing-indicator">
              <div className="typing-dot" />
              <div className="typing-dot" />
              <div className="typing-dot" />
            </div>
          </div>
        )}
      </div>

      {/* ── Input Workspace ── */}
      <div className="chat-input-area">
        <div className="chat-input-row">
          <textarea
            ref={inputRef}
            className="chat-input"
            placeholder="Ask about deposits, debits, categories, or balance trends..."
            rows={1}
            value={input}
            onChange={onInputChange}
            onKeyDown={onKeyDown}
            disabled={busy}
            aria-label="Chat message"
          />
          <button
            className="send-btn"
            onClick={() => handleSend()}
            disabled={busy || !input.trim()}
            aria-label="Send message"
            title="Send (Enter)"
          >
            {/* Elegant Send icon */}
            <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}
