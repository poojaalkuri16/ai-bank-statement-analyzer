import React, { useState } from 'react'
import UploadView from './UploadView'
import ChatView   from './ChatView'

/**
 * App — top-level router.
 *
 * Two views:
 *   upload  — PDF dropzone (initial state)
 *   chat    — conversation interface for an active session
 *
 * No URL routing needed for this single-user local demo.
 */
export default function App() {
  const [view, setView]       = useState('upload')
  const [session, setSession] = useState(null)
  // session = { sessionId, summary, suggestions }

  const handleSessionReady = (sessionData) => {
    setSession(sessionData)
    setView('chat')
  }

  const handleNewStatement = () => {
    setSession(null)
    setView('upload')
  }

  return (
    <div className="app-container">
      {/* Dynamic background glow shapes */}
      <div className="glow-blob glow-blob-1" />
      <div className="glow-blob glow-blob-2" />
      <div className="glow-blob glow-blob-3" />

      {view === 'chat' && session ? (
        <ChatView
          sessionId={session.sessionId}
          summary={session.summary}
          suggestions={session.suggestions}
          onNewStatement={handleNewStatement}
        />
      ) : (
        <UploadView onSessionReady={handleSessionReady} />
      )}
    </div>
  )
}
