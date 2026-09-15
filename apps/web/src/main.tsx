import React from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

type Message = { id: number; sender: string; body: string; bot?: boolean };

function App() {
  const [draft, setDraft] = React.useState('');
  const [messages, setMessages] = React.useState<Message[]>([
    { id: 1, sender: 'Minh', body: 'Profile the January sales file and show quality issues.' },
    { id: 2, sender: 'DataSteward', body: 'I can import and profile the approved source. I will ask before metadata decisions.', bot: true },
  ]);
  const send = () => {
    const body = draft.trim();
    if (!body) return;
    setMessages((current) => [...current, { id: Date.now(), sender: 'Minh', body }]);
    setDraft('');
  };
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand">VDaAgent</div>
      <div className="workspace">Workspace / Sales</div>
      <button className="room active"># sales-profiling <span>3</span></button>
      <button className="room"># data-quality</button>
      <button className="room">DM · DataAnalyst</button>
      <div className="sidebar-bottom">R1 local shell<br /><small>OIDC/API integration follows M1.</small></div>
    </aside>
    <main className="chat-pane">
      <header className="chat-header"><div><strong># sales-profiling</strong><small>3 humans · 3 bots · workspace-scoped</small></div><button>Observatory</button></header>
      <div className="bot-strip"><span className="bot-chip assistant">DataAssistant</span><span className="bot-chip steward">DataSteward</span><span className="bot-chip analyst">DataAnalyst</span><span className="bot-chip writer">ReportWriter</span></div>
      <section className="messages" aria-label="conversation">
        {messages.map((message) => <article className={`message ${message.bot ? 'bot-message' : ''}`} key={message.id}><div className="avatar">{message.sender.slice(0, 1)}</div><div><div className="sender">{message.sender}{message.bot && <span className="bot-label">BOT</span>}</div><p>{message.body}</p>{message.bot && <div className="evidence-card"><strong>Profile job queued</strong><span>source: sales_january.csv · run: pending</span><span>evidence will appear after approved compute</span></div>}</div></article>)}
      </section>
      <div className="composer"><textarea value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); send(); } }} placeholder="Message the room or @mention a bot…" aria-label="message" /><button onClick={send}>Send</button></div>
    </main>
    <aside className="inspector"><h2>Data & Observatory</h2><section><h3>Dataset</h3><div className="dataset-card"><strong>sales_january.csv</strong><span>immutable source · ready</span><span>3 rows · 5 columns · 1 PII field</span></div></section><section><h3>Run activity</h3><ol className="timeline"><li><b>Message committed</b><small>human ACK · event #12</small></li><li><b>DataSteward</b><small>profile.start · queued</small></li><li><b>Evidence</b><small>waiting for compute result</small></li></ol></section><section className="privacy-note">Only metadata is shown in Observatory. Raw prompts, secrets and private memory are never captured.</section></aside>
  </div>;
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>);
