/**
 * useElectron Hook
 * 
 * 提供对 Electron API 的安全访问
 * 在浏览器环境中返回空操作
 */

import { useEffect, useCallback, useState } from 'react'

interface ElectronAPI {
  // 窗口控制
  minimize: () => void
  maximize: () => void
  close: () => void
  
  // 平台信息
  platform: string
  isElectron: boolean
  
  // 事件监听
  onNewSession: (callback: () => void) => () => void
  onToggleCommandPalette: (callback: () => void) => () => void
  
  // 主进程通信
  toggleCommandPalette: () => void
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI
  }
}

export function useElectron() {
  const [isElectron, setIsElectron] = useState(false)
  const [platform, setPlatform] = useState<string>('web')

  useEffect(() => {
    const api = window.electronAPI
    if (api?.isElectron) {
      setIsElectron(true)
      setPlatform(api.platform || 'unknown')
    }
  }, [])

  // 窗口控制
  const minimize = useCallback(() => {
    window.electronAPI?.minimize?.()
  }, [])

  const maximize = useCallback(() => {
    window.electronAPI?.maximize?.()
  }, [])

  const close = useCallback(() => {
    window.electronAPI?.close?.()
  }, [])

  // 命令面板
  const toggleCommandPalette = useCallback(() => {
    window.electronAPI?.toggleCommandPalette?.()
  }, [])

  // 事件监听
  const onNewSession = useCallback((callback: () => void) => {
    const api = window.electronAPI
    if (api?.onNewSession) {
      return api.onNewSession(callback)
    }
    return () => {}
  }, [])

  const onToggleCommandPalette = useCallback((callback: () => void) => {
    const api = window.electronAPI
    if (api?.onToggleCommandPalette) {
      return api.onToggleCommandPalette(callback)
    }
    return () => {}
  }, [])

  return {
    isElectron,
    platform,
    isMac: platform === 'darwin',
    isWindows: platform === 'win32',
    isLinux: platform === 'linux',
    
    // 窗口控制
    minimize,
    maximize,
    close,
    
    // 命令面板
    toggleCommandPalette,
    
    // 事件监听
    onNewSession,
    onToggleCommandPalette,
  }
}

export default useElectron

