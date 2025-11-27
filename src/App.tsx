// src/App.tsx
import React from 'react';
import Layout from './components/Layout';
import DocumentsPage from './pages/DocumentsPage';

function App() {
  return (
    <Layout>
      <DocumentsPage />
    </Layout>
  );
}

export default App;