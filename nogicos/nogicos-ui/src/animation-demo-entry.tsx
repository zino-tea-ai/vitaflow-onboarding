/**
 * Animation Demo Entry Point
 * 独立的动画演示入口
 */

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { AnimationPrimitivesDemo } from './components/animation-primitives'
import './components/animation-primitives/animation-demo.css'

createRoot(document.getElementById('animation-demo-root')!).render(
  <StrictMode>
    <AnimationPrimitivesDemo />
  </StrictMode>,
)

