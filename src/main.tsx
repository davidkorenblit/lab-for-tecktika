import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '@/lib/queryClient';
import { JobsProvider } from '@/providers/JobsProvider';
import App from './App';
import './index.css';

const container = document.getElementById('root');
if (!container) throw new Error('Root element not found');

createRoot(container).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      {/* Above the app: job polling must keep running no matter which view is open. */}
      <JobsProvider>
        <App />
      </JobsProvider>
    </QueryClientProvider>
  </StrictMode>,
);
