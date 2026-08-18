// 시도 2: `astryx docs theme --dense` 출력대로 수정 (pre-built CSS 방식).
import '@astryxdesign/core/reset.css';
import '@astryxdesign/core/astryx.css';
import '@astryxdesign/theme-neutral/theme.css';

import {Theme} from '@astryxdesign/core';
import {neutralTheme} from '@astryxdesign/theme-neutral/built';
import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';

import App from './App';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Theme theme={neutralTheme}>
      <App />
    </Theme>
  </StrictMode>,
);
