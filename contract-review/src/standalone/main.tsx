import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import '../theme/vizient-theme.css';
import '../about/about.css';
import './standalone.css';
import { StandalonePage } from './StandalonePage';

const root = document.getElementById('root');
if (!root) throw new Error('The page has no #root element.');

createRoot(root).render(
  <StrictMode>
    <StandalonePage />
  </StrictMode>,
);
