import React from 'react';
import { createRoot } from 'react-dom/client';

function App() {
  return <main><h1>VDaAgent</h1><p>R1 demo shell — authenticated workspace UI is implemented in M1.</p></main>;
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>);
