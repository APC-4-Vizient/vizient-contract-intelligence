import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { FluentProvider } from '@fluentui/react-components';
import './theme/vizient-theme.css';
import './app.css';
import { App } from './App';
import { vizientTheme } from './theme/vizient-fluent-theme';

const root = document.getElementById('root');
if (!root) throw new Error('The page has no #root element.');

createRoot(root).render(
  <StrictMode>
    <FluentProvider theme={vizientTheme}>
      <App />
    </FluentProvider>
  </StrictMode>,
);
