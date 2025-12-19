'use client'

import { useEffect, useCallback, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  type DropAnimation,
  defaultDropAnimationSideEffects,
} from '@dnd-kit/core'
import {
  SortableContext,
  sortableKeyboardCoordinates,
  rectSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { AppLayout } from '@/components/layout'
import { PreviewPanel, ShortcutsHint, StatusBar, PendingPanel } from '@/components/sort'
import { useProjectStore } from '@/store/project-store'
import { useSortStore } from '@/store/sort-store'
import { getThumbnailUrl, importScreenshot, uploadScreenshot } from '@/lib/api'
import type { Screenshot, Project } from '@/types'
import {
  ArrowUpDown,
  Save,
  Check,
  Trash2,
  RotateCcw,
  CheckSquare,
  Square,
  X,
  Play,
  Flag,
  ChevronDown,
  ZoomIn,
  ZoomOut,
  Maximize2,
} from 'lucide-react'
import { toast } from 'sonner'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

// 缩放配置
const ZOOM_MIN = 50
const ZOOM_MAX = 200
const ZOOM_STEP = 25
const ZOOM_DEFAULT = 100

// 优化的 dropAnimation 配置
const dropAnimation: DropAnimation = {
  sideEffects: defaultDropAnimationSideEffects({
    styles: {
      active: {
        opacity: '0.5',
      },
    },
  }),
  duration: 250,
  easing: 'cubic-bezier(0.25, 1, 0.5, 1)',
}

// 根据缩放计算卡片最小宽度
function getCardMinWidth(zoom: number): number {
  const baseWidth = 100 // 默认 100px
  return Math.round(baseWidth * (zoom / 100))
}

// Logo URL helper
function getLogoUrl(projectName: string): string {
  const appName = projectName.includes('/') 
    ? projectName.split('/').pop() 
    : projectName
  return `${API_BASE}/api/logo/${appName}`
}

// 自定义项目选择器组件
function ProjectSelector({
  projects,
  selectedProject,
  onSelect,
}: {
  projects: Project[]
  selectedProject: string | null
  onSelect: (name: string | null) => void
}) {
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // 点击外部关闭
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const selectedProjectData = projects.find(p => p.name === selectedProject)

  return (
    <div ref={dropdownRef} style={{ position: 'relative', minWidth: '240px' }}>
      {/* 触发按钮 */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          width: '100%',
          padding: '8px 12px',
          borderRadius: '8px',
          background: 'var(--bg-secondary)',
          color: 'var(--text-primary)',
          border: '1px solid var(--border-default)',
          fontSize: '14px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
        }}
      >
        {selectedProjectData ? (
          <>
            <img
              src={getLogoUrl(selectedProjectData.name)}
              alt={selectedProjectData.display_name}
              style={{
                width: '24px',
                height: '24px',
                borderRadius: '5px',
                objectFit: 'cover',
              }}
              onError={(e) => {
                const target = e.target as HTMLImageElement
                target.style.display = 'none'
              }}
            />
            <span style={{ flex: 1, textAlign: 'left' }}>
              {selectedProjectData.display_name}
            </span>
            <span style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>
              ({selectedProjectData.screen_count})
            </span>
          </>
        ) : (
          <span style={{ flex: 1, textAlign: 'left', color: 'var(--text-secondary)' }}>
            选择项目...
          </span>
        )}
        <ChevronDown size={16} style={{ opacity: 0.5 }} />
      </button>

      {/* 下拉列表 */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.15 }}
            style={{
              position: 'absolute',
              top: '100%',
              left: 0,
              right: 0,
              marginTop: '4px',
              background: '#1a1a1a',
              border: '1px solid var(--border-default)',
              borderRadius: '8px',
              boxShadow: '0 10px 40px rgba(0,0,0,0.5)',
              maxHeight: '400px',
              overflowY: 'auto',
              zIndex: 100,
            }}
          >
            {projects.map((project) => (
              <button
                key={project.name}
                onClick={() => {
                  onSelect(project.name)
                  setIsOpen(false)
                }}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  background: selectedProject === project.name ? 'rgba(255,255,255,0.08)' : 'transparent',
                  border: 'none',
                  borderBottom: '1px solid rgba(255,255,255,0.04)',
                  color: '#fff',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  fontSize: '13px',
                  textAlign: 'left',
                }}
              >
                <img
                  src={getLogoUrl(project.name)}
                  alt={project.display_name}
                  style={{
                    width: '28px',
                    height: '28px',
                    borderRadius: '6px',
                    objectFit: 'cover',
                  }}
                  onError={(e) => {
                    const target = e.target as HTMLImageElement
                    target.style.display = 'none'
                  }}
                />
                <span style={{ flex: 1 }}>{project.display_name}</span>
                <span style={{ color: '#6b7280', fontSize: '12px' }}>
                  {project.screen_count}
                </span>
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// 可排序的截图卡片
function SortableScreenshot({
  screenshot,
  projectName,
  index,
  isSelected,
  isNewlyAdded,
  onCardClick,
  onboardingStart,
  onboardingEnd,
}: {
  screenshot: Screenshot
  projectName: string
  index: number
  isSelected: boolean
  isNewlyAdded?: boolean
  onCardClick: (e: React.MouseEvent) => void
  onboardingStart: number
  onboardingEnd: number
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ 
    id: screenshot.filename,
    transition: {
      duration: 200,
      easing: 'cubic-bezier(0.25, 1, 0.5, 1)',
    },
  })

  const isInOnboarding =
    onboardingStart >= 0 &&
    onboardingEnd >= 0 &&
    index >= onboardingStart &&
    index <= onboardingEnd

  const isStart = index === onboardingStart
  const isEnd = index === onboardingEnd

  const style = {
    transform: CSS.Transform.toString(transform),
    transition: transition || 'transform 200ms cubic-bezier(0.25, 1, 0.5, 1)',
    opacity: isDragging ? 0.3 : 1,
    zIndex: isDragging ? 100 : 'auto',
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="screenshot-card"
      {...attributes}
    >
      <div
        onClick={onCardClick}
        style={{
          position: 'relative',
          aspectRatio: '9/16',
          overflow: 'hidden',
          background: 'var(--bg-secondary)',
          cursor: 'pointer',
          border: isDragging
            ? '2px dashed rgba(255,255,255,0.4)'
            : isNewlyAdded
              ? '3px solid #f59e0b'
              : isSelected
                ? '3px solid #3b82f6'
                : isInOnboarding
                  ? '2px solid #22c55e'
                  : '2px solid rgba(255,255,255,0.15)',
          borderRadius: '6px',
          boxShadow: isNewlyAdded 
            ? '0 0 20px rgba(245, 158, 11, 0.5)' 
            : isSelected
              ? '0 0 0 2px rgba(59, 130, 246, 0.5)'
              : isDragging
                ? '0 20px 40px rgba(0, 0, 0, 0.4)'
                : undefined,
          animation: isNewlyAdded ? 'pulse 1s ease-in-out infinite' : undefined,
          transition: 'border 150ms, box-shadow 150ms',
        }}
      >
        {/* Drag Handle */}
        <div
          {...listeners}
          style={{
            position: 'absolute',
            inset: 0,
            cursor: isDragging ? 'grabbing' : 'grab',
          }}
        />

        <img
          src={getThumbnailUrl(projectName, screenshot.filename, 'small')}
          alt={screenshot.filename}
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            pointerEvents: 'none',
          }}
          loading="lazy"
        />

        {/* 选中遮罩和勾选图标 */}
        {isSelected && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              background: 'rgba(59, 130, 246, 0.35)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              pointerEvents: 'none',
            }}
          >
            <div
              style={{
                width: '40px',
                height: '40px',
                borderRadius: '50%',
                background: '#fff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
              }}
            >
              <Check size={24} style={{ color: '#3b82f6' }} />
            </div>
          </div>
        )}

        {/* 索引 */}
        <div
          style={{
            position: 'absolute',
            top: '4px',
            left: '4px',
            padding: '2px 6px',
            background: 'rgba(0, 0, 0, 0.7)',
            borderRadius: '4px',
            fontSize: '10px',
            color: 'var(--text-secondary)',
            fontFamily: 'var(--font-mono)',
          }}
        >
          {String(index + 1).padStart(4, '0')}
        </div>

        {/* START/END 标记 */}
        {isStart && (
          <div
            style={{
              position: 'absolute',
              bottom: '4px',
              left: '4px',
              padding: '2px 6px',
              background: '#22c55e',
              borderRadius: '4px',
              fontSize: '9px',
              color: '#fff',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: '2px',
            }}
          >
            <Play size={8} /> START
          </div>
        )}
        {isEnd && (
          <div
            style={{
              position: 'absolute',
              bottom: '4px',
              left: '4px',
              padding: '2px 6px',
              background: '#f59e0b',
              borderRadius: '4px',
              fontSize: '9px',
              color: '#fff',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: '2px',
            }}
          >
            <Flag size={8} /> END
          </div>
        )}

        {/* Onboarding 范围内标记 */}
        {isInOnboarding && !isStart && !isEnd && (
          <div
            style={{
              position: 'absolute',
              bottom: '4px',
              left: '4px',
              width: '6px',
              height: '6px',
              background: '#22c55e',
              borderRadius: '50%',
            }}
          />
        )}

        {/* 新添加标记 */}
        {isNewlyAdded && (
          <div
            style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              padding: '4px 8px',
              background: '#f59e0b',
              borderRadius: '4px',
              fontSize: '10px',
              color: '#fff',
              fontWeight: 700,
              textTransform: 'uppercase',
            }}
          >
            NEW
          </div>
        )}
      </div>
    </div>
  )
}

// 拖拽时的预览
function DragPreview({
  screenshot,
  projectName,
  zoom = 100,
}: {
  screenshot: Screenshot
  projectName: string
  zoom?: number
}) {
  const previewWidth = Math.round(120 * (zoom / 100))
  
  return (
    <motion.div
      className="screenshot-card"
      initial={{ scale: 1, rotate: 0 }}
      animate={{ scale: 1.05, rotate: 2 }}
      transition={{ duration: 0.15, ease: 'easeOut' }}
      style={{
        width: `${previewWidth}px`,
        boxShadow: '0 20px 40px rgba(0, 0, 0, 0.5), 0 0 0 2px rgba(255,255,255,0.8)',
        borderRadius: '8px',
        overflow: 'hidden',
        cursor: 'grabbing',
      }}
    >
      <div
        style={{
          aspectRatio: '9/16',
          overflow: 'hidden',
          background: 'var(--bg-secondary)',
        }}
      >
        <img
          src={getThumbnailUrl(projectName, screenshot.filename, 'small')}
          alt={screenshot.filename}
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            pointerEvents: 'none',
          }}
        />
      </div>
      
      {/* 拖拽时的标识 */}
      <div
        style={{
          position: 'absolute',
          bottom: '4px',
          left: '50%',
          transform: 'translateX(-50%)',
          padding: '2px 8px',
          background: 'rgba(0,0,0,0.8)',
          borderRadius: '4px',
          fontSize: '10px',
          color: '#fff',
          fontWeight: 500,
          whiteSpace: 'nowrap',
        }}
      >
        拖拽中...
      </div>
    </motion.div>
  )
}

export default function SortPage() {
  const { projects, fetchProjects, loading: projectsLoading } = useProjectStore()
  const {
    sortedScreenshots,
    deletedBatches,
    selectedFiles,
    onboardingRange,
    previewIndex,
    loading,
    saving,
    error,
    hasChanges,
    fetchData,
    reorder,
    toggleSelect,
    selectAll,
    deselectAll,
    setSelectedFiles,
    deleteSelected,
    restoreBatch,
    saveSortOrder,
    applySortOrder,
    setPreviewIndex,
    prevPreview,
    nextPreview,
    reset,
  } = useSortStore()

  const [selectedProject, setSelectedProject] = useState<string | null>(null)
  const [lastClickedIndex, setLastClickedIndex] = useState<number | null>(null)
  const [activeId, setActiveId] = useState<string | null>(null)
  const [showDeleted, setShowDeleted] = useState(false)
  const [isDragOver, setIsDragOver] = useState(false)
  const [dropTargetIndex, setDropTargetIndex] = useState<number | null>(null)
  const [uploadMessage, setUploadMessage] = useState<string | null>(null)
  const [newlyAdded, setNewlyAdded] = useState<string | null>(null)
  const [zoom, setZoom] = useState(ZOOM_DEFAULT)
  const contentRef = useRef<HTMLDivElement>(null)
  const gridRef = useRef<HTMLDivElement>(null)

  // 缩放控制函数
  const zoomIn = useCallback(() => {
    setZoom(prev => Math.min(prev + ZOOM_STEP, ZOOM_MAX))
  }, [])
  
  const zoomOut = useCallback(() => {
    setZoom(prev => Math.max(prev - ZOOM_STEP, ZOOM_MIN))
  }, [])
  
  const resetZoom = useCallback(() => {
    setZoom(ZOOM_DEFAULT)
  }, [])

  // dnd-kit sensors
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  )

  // 加载项目列表
  useEffect(() => {
    fetchProjects()
  }, [fetchProjects])

  // 离开页面提示（如果有未保存的更改）
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasChanges) {
        e.preventDefault()
        e.returnValue = '你有未保存的排序更改，确定要离开吗？'
        return e.returnValue
      }
    }

    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [hasChanges])

  // 切换项目时加载数据
  useEffect(() => {
    if (selectedProject) {
      fetchData(selectedProject)
    } else {
      reset()
    }
  }, [selectedProject, fetchData, reset])

  // 滚轮缩放 (Ctrl + 滚轮)
  useEffect(() => {
    if (!selectedProject) return
    
    const handleWheel = (e: WheelEvent) => {
      if (e.ctrlKey) {
        e.preventDefault()
        if (e.deltaY < 0) {
          zoomIn()
        } else {
          zoomOut()
        }
      }
    }
    
    const contentArea = contentRef.current
    if (contentArea) {
      contentArea.addEventListener('wheel', handleWheel, { passive: false })
      return () => contentArea.removeEventListener('wheel', handleWheel)
    }
  }, [selectedProject, zoomIn, zoomOut])

  // 全局快捷键
  useEffect(() => {
    if (!selectedProject) return

    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl+A 全选
      if (e.ctrlKey && e.key === 'a') {
        e.preventDefault()
        selectAll()
      }
      // Ctrl++ 放大
      if (e.ctrlKey && (e.key === '=' || e.key === '+')) {
        e.preventDefault()
        zoomIn()
      }
      // Ctrl+- 缩小
      if (e.ctrlKey && e.key === '-') {
        e.preventDefault()
        zoomOut()
      }
      // Ctrl+0 重置缩放
      if (e.ctrlKey && e.key === '0') {
        e.preventDefault()
        resetZoom()
      }
      // Delete 删除选中 - 需要确认
      if (e.key === 'Delete' && selectedFiles.size > 0) {
        const count = selectedFiles.size
        if (count > 10) {
          // 删除超过10张需要确认
          if (window.confirm(`确定要删除 ${count} 张截图吗？此操作可以从"已删除"中恢复。`)) {
            deleteSelected(selectedProject)
          }
        } else {
          deleteSelected(selectedProject)
        }
      }
      // Escape 取消选择
      if (e.key === 'Escape') {
        deselectAll()
        setPreviewIndex(null)
      }
      // 左箭头 上一张
      if (e.key === 'ArrowLeft' && previewIndex !== null) {
        prevPreview()
      }
      // 右箭头 下一张
      if (e.key === 'ArrowRight' && previewIndex !== null) {
        nextPreview()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [
    selectedProject,
    selectedFiles,
    previewIndex,
    selectAll,
    deselectAll,
    deleteSelected,
    setPreviewIndex,
    prevPreview,
    nextPreview,
    zoomIn,
    zoomOut,
    resetZoom,
  ])

  // 处理拖拽开始
  const handleDragStart = useCallback((event: DragStartEvent) => {
    setActiveId(event.active.id as string)
  }, [])

  // 处理拖拽结束
  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event
      setActiveId(null)

      if (over && active.id !== over.id) {
        const oldIndex = sortedScreenshots.findIndex(
          (s) => s.filename === active.id
        )
        const newIndex = sortedScreenshots.findIndex(
          (s) => s.filename === over.id
        )
        reorder(oldIndex, newIndex)
      }
    },
    [sortedScreenshots, reorder]
  )

  // 当前拖拽的截图
  const activeScreenshot = activeId
    ? sortedScreenshots.find((s) => s.filename === activeId)
    : null

  // 当前预览的截图
  const previewScreenshot =
    previewIndex !== null ? sortedScreenshots[previewIndex] : null

  // 计算已移动数量 (简化版，后续可以优化)
  const movedCount = hasChanges ? 1 : 0

  // 提取显示名称
  const displayProjectName = selectedProject
    ? selectedProject.replace('downloads_2024/', '')
    : ''

  // 导入成功后刷新数据
  const handleImportSuccess = useCallback(() => {
    if (selectedProject) {
      fetchData(selectedProject)
    }
  }, [selectedProject, fetchData])

  // 处理卡片点击 - 合并选中和预览行为
  const handleCardClick = useCallback((e: React.MouseEvent, index: number, filename: string) => {
    // 始终更新预览
    setPreviewIndex(index)
    
    if (e.shiftKey && lastClickedIndex !== null) {
      // Shift+点击：范围选中
      const start = Math.min(lastClickedIndex, index)
      const end = Math.max(lastClickedIndex, index)
      const filesToSelect = sortedScreenshots.slice(start, end + 1).map(s => s.filename)
      setSelectedFiles(new Set(filesToSelect))
    } else if (e.ctrlKey || e.metaKey) {
      // Ctrl/Cmd+点击：切换选中（多选）
      toggleSelect(filename)
    } else {
      // 普通点击：只选中这一张（清除其他）
      setSelectedFiles(new Set([filename]))
    }
    
    setLastClickedIndex(index)
  }, [lastClickedIndex, sortedScreenshots, setPreviewIndex, setSelectedFiles, toggleSelect])

  // 处理拖拽进入 - 计算插入位置
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (!selectedProject) return
    
    // 检查是否是文件或待处理截图
    const hasFiles = e.dataTransfer.types.includes('Files')
    const hasPending = e.dataTransfer.types.includes('application/x-pending-screenshot')
    
    if (hasFiles || hasPending) {
      setIsDragOver(true)
      e.dataTransfer.dropEffect = 'copy'
      
      // 计算插入位置
      if (gridRef.current) {
        const gridRect = gridRef.current.getBoundingClientRect()
        const cards = gridRef.current.querySelectorAll('[data-screenshot-card]')
        
        let targetIndex = sortedScreenshots.length // 默认末尾
        
        for (let i = 0; i < cards.length; i++) {
          const card = cards[i] as HTMLElement
          const rect = card.getBoundingClientRect()
          const cardCenterX = rect.left + rect.width / 2
          const cardCenterY = rect.top + rect.height / 2
          
          // 如果鼠标在卡片左半边，插入到该位置之前
          if (e.clientY < rect.bottom && e.clientY > rect.top - 20) {
            if (e.clientX < cardCenterX) {
              targetIndex = i
              break
            } else if (i === cards.length - 1 || e.clientX < rect.right) {
              targetIndex = i + 1
              break
            }
          }
        }
        
        setDropTargetIndex(targetIndex)
      }
    }
  }, [selectedProject, sortedScreenshots.length])

  // 处理拖拽离开
  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    // 只有当真正离开内容区域时才重置
    const relatedTarget = e.relatedTarget as HTMLElement
    if (!contentRef.current?.contains(relatedTarget)) {
      setIsDragOver(false)
      setDropTargetIndex(null)
    }
  }, [])

  // 处理文件放下
  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    
    const targetIndex = dropTargetIndex ?? sortedScreenshots.length
    setIsDragOver(false)
    setDropTargetIndex(null)
    
    if (!selectedProject) {
      toast.error('请先选择一个项目')
      return
    }

    // 处理待处理区拖来的截图
    const pendingData = e.dataTransfer.getData('application/x-pending-screenshot')
    if (pendingData) {
      try {
        const { filename } = JSON.parse(pendingData)
        const result = await importScreenshot(selectedProject, filename)
        if (result.success && result.new_filename) {
          // 【优化】不再 fetchData，直接在本地状态中添加新截图（乐观更新）
          const newScreenshot: Screenshot = {
            filename: result.new_filename,
            path: '', // 路径由后端管理
          }
          
          // 直接插入到指定位置
          const currentScreenshots = useSortStore.getState().sortedScreenshots
          const reordered = [
            ...currentScreenshots.slice(0, targetIndex),
            newScreenshot,
            ...currentScreenshots.slice(targetIndex)
          ]
          useSortStore.setState({ sortedScreenshots: reordered, hasChanges: true })
          
          if (targetIndex < currentScreenshots.length) {
            setUploadMessage(`✓ 已插入 ${result.new_filename} 到位置 ${targetIndex + 1}`)
          } else {
            setUploadMessage(`✓ 已导入 ${result.new_filename} 到末尾`)
          }
          
          setNewlyAdded(result.new_filename)
          setTimeout(() => {
            setUploadMessage(null)
            setNewlyAdded(null)
          }, 3000)
        }
      } catch (error) {
        toast.error('导入失败: ' + (error as Error).message)
      }
      return
    }

    // 处理外部文件
    const files = Array.from(e.dataTransfer.files).filter(f => 
      f.type.startsWith('image/') || 
      /\.(png|jpg|jpeg|webp)$/i.test(f.name)
    )

    if (files.length === 0) {
      toast.error('请拖入图片文件')
      return
    }

    // 逐个上传
    const uploadedFiles: string[] = []
    for (const file of files) {
      try {
        const result = await uploadScreenshot(selectedProject, file)
        if (result.success && result.new_filename) {
          uploadedFiles.push(result.new_filename)
        }
      } catch (error) {
        console.error('Upload failed:', error)
      }
    }

    if (uploadedFiles.length > 0) {
      // 【优化】不再 fetchData，直接在本地状态中添加新截图（乐观更新）
      const newScreenshots: Screenshot[] = uploadedFiles.map(filename => ({
        filename,
        path: '',
      }))
      
      const currentScreenshots = useSortStore.getState().sortedScreenshots
      const reordered = [
        ...currentScreenshots.slice(0, targetIndex),
        ...newScreenshots,
        ...currentScreenshots.slice(targetIndex)
      ]
      useSortStore.setState({ sortedScreenshots: reordered, hasChanges: true })
      
      if (targetIndex < currentScreenshots.length) {
        setUploadMessage(`✓ 已插入 ${uploadedFiles.length} 张截图到位置 ${targetIndex + 1}`)
      } else {
        setUploadMessage(`✓ 已导入 ${uploadedFiles.length} 张截图到末尾`)
      }
      
      setNewlyAdded(uploadedFiles[uploadedFiles.length - 1])
      setTimeout(() => {
        setUploadMessage(null)
        setNewlyAdded(null)
      }, 3000)
    }
  }, [selectedProject, dropTargetIndex, sortedScreenshots.length])

  return (
    <AppLayout>
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* 左侧待处理区 */}
        <div
          style={{
            width: '280px',
            flexShrink: 0,
            borderRight: '1px solid var(--border-default)',
            overflowY: 'auto',
            padding: '12px',
          }}
        >
          <PendingPanel
            selectedProject={selectedProject}
            onImportSuccess={handleImportSuccess}
          />
        </div>

        {/* 主内容区 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* 顶栏 */}
          <div className="topbar">
            <h1 className="topbar-title">截图排序</h1>
            <div style={{ flex: 1 }} />

            {/* 缩放控制 */}
            {selectedProject && sortedScreenshots.length > 0 && (
              <div 
                style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '4px',
                  padding: '4px 8px',
                  background: 'var(--bg-secondary)',
                  borderRadius: '8px',
                  marginRight: '12px',
                }}
              >
                <button
                  onClick={zoomOut}
                  disabled={zoom <= ZOOM_MIN}
                  style={{
                    padding: '4px',
                    background: 'transparent',
                    border: 'none',
                    borderRadius: '4px',
                    color: zoom <= ZOOM_MIN ? 'var(--text-muted)' : 'var(--text-secondary)',
                    cursor: zoom <= ZOOM_MIN ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    transition: 'color 150ms, background 150ms',
                  }}
                  onMouseEnter={(e) => zoom > ZOOM_MIN && (e.currentTarget.style.background = 'rgba(255,255,255,0.1)')}
                  onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                  title="缩小 (Ctrl+-)"
                >
                  <ZoomOut size={16} />
                </button>
                
                <button
                  onClick={resetZoom}
                  style={{
                    padding: '2px 8px',
                    background: zoom !== ZOOM_DEFAULT ? 'rgba(59, 130, 246, 0.2)' : 'transparent',
                    border: 'none',
                    borderRadius: '4px',
                    color: 'var(--text-primary)',
                    cursor: 'pointer',
                    fontSize: '12px',
                    fontFamily: 'var(--font-mono)',
                    fontWeight: 500,
                    minWidth: '48px',
                    transition: 'background 150ms',
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.1)'}
                  onMouseLeave={(e) => e.currentTarget.style.background = zoom !== ZOOM_DEFAULT ? 'rgba(59, 130, 246, 0.2)' : 'transparent'}
                  title="重置缩放 (Ctrl+0)"
                >
                  {zoom}%
                </button>
                
                <button
                  onClick={zoomIn}
                  disabled={zoom >= ZOOM_MAX}
                  style={{
                    padding: '4px',
                    background: 'transparent',
                    border: 'none',
                    borderRadius: '4px',
                    color: zoom >= ZOOM_MAX ? 'var(--text-muted)' : 'var(--text-secondary)',
                    cursor: zoom >= ZOOM_MAX ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    transition: 'color 150ms, background 150ms',
                  }}
                  onMouseEnter={(e) => zoom < ZOOM_MAX && (e.currentTarget.style.background = 'rgba(255,255,255,0.1)')}
                  onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                  title="放大 (Ctrl++)"
                >
                  <ZoomIn size={16} />
                </button>
              </div>
            )}

            {/* 项目选择器 */}
            <ProjectSelector
              projects={projects}
              selectedProject={selectedProject}
              onSelect={setSelectedProject}
            />

            {/* 操作按钮 */}
            {selectedProject && sortedScreenshots.length > 0 && (
              <div style={{ display: 'flex', gap: '8px', marginLeft: '16px' }}>
                {/* 选择操作 */}
                <button
                  className="btn-ghost"
                  onClick={() =>
                    selectedFiles.size > 0 ? deselectAll() : selectAll()
                  }
                >
                  {selectedFiles.size > 0 ? (
                    <>
                      <X size={16} />
                      取消 ({selectedFiles.size})
                    </>
                  ) : (
                    <>
                      <CheckSquare size={16} />
                      全选
                    </>
                  )}
                </button>

                {/* 删除选中 */}
                {selectedFiles.size > 0 && (
                  <button
                    className="btn-ghost"
                    onClick={() => {
                      if (!selectedProject) return
                      const count = selectedFiles.size
                      if (count > 10) {
                        if (window.confirm(`确定要删除 ${count} 张截图吗？此操作可以从"已删除"中恢复。`)) {
                          deleteSelected(selectedProject)
                        }
                      } else {
                        deleteSelected(selectedProject)
                      }
                    }}
                    disabled={saving}
                    style={{ color: 'var(--danger)' }}
                  >
                    <Trash2 size={16} />
                    删除 ({selectedFiles.size})
                  </button>
                )}

                {/* 已删除 */}
                {deletedBatches.length > 0 && (
                  <button
                    className={`btn-ghost ${showDeleted ? 'active' : ''}`}
                    onClick={() => setShowDeleted(!showDeleted)}
                  >
                    <RotateCcw size={16} />
                    已删除 ({deletedBatches.reduce((a, b) => a + b.count, 0)})
                  </button>
                )}

                {/* 保存排序 */}
                {hasChanges && (
                  <>
                    <button
                      className="btn-ghost"
                      onClick={() => selectedProject && saveSortOrder(selectedProject)}
                      disabled={saving}
                    >
                      <Save size={16} />
                      保存排序
                    </button>

                    <button
                      className="btn-ghost"
                      onClick={() => selectedProject && applySortOrder(selectedProject)}
                      disabled={saving}
                      style={{
                        background: 'var(--success)',
                        color: '#fff',
                      }}
                    >
                      <Check size={16} />
                      {saving ? '应用中...' : '应用并重命名'}
                    </button>
                  </>
                )}
              </div>
            )}
          </div>

          {/* 状态栏 */}
          {selectedProject && sortedScreenshots.length > 0 && (
            <StatusBar
              projectName={displayProjectName}
              total={sortedScreenshots.length}
              selected={selectedFiles.size}
              moved={movedCount}
              onboardingStart={onboardingRange.start}
              onboardingEnd={onboardingRange.end}
            />
          )}

          {/* 内容区 */}
          <div 
            ref={contentRef}
            className="content-area" 
            style={{ 
              flex: 1, 
              overflow: 'auto',
              position: 'relative',
            }}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            {/* 拖拽提示覆盖层 */}
            {isDragOver && (
              <div
                style={{
                  position: 'absolute',
                  inset: 0,
                  background: 'rgba(245, 158, 11, 0.05)',
                  border: '3px dashed #f59e0b',
                  borderRadius: '12px',
                  zIndex: 5,
                  display: 'flex',
                  alignItems: 'flex-start',
                  justifyContent: 'center',
                  paddingTop: '20px',
                  pointerEvents: 'none',
                }}
              >
                <div style={{
                  background: 'rgba(0,0,0,0.9)',
                  padding: '12px 24px',
                  borderRadius: '8px',
                  color: '#f59e0b',
                  fontSize: '14px',
                  fontWeight: 500,
                }}>
                  {dropTargetIndex !== null && dropTargetIndex < sortedScreenshots.length
                    ? `释放插入到位置 ${dropTargetIndex + 1}`
                    : '释放添加到末尾'}
                </div>
              </div>
            )}
            
            {/* 上传成功提示 */}
            {uploadMessage && (
              <div
                style={{
                  position: 'fixed',
                  bottom: '24px',
                  left: '50%',
                  transform: 'translateX(-50%)',
                  background: '#22c55e',
                  color: '#fff',
                  padding: '12px 24px',
                  borderRadius: '8px',
                  fontSize: '14px',
                  fontWeight: 500,
                  zIndex: 100,
                  boxShadow: '0 4px 20px rgba(34, 197, 94, 0.4)',
                }}
              >
                {uploadMessage}
              </div>
            )}
            {/* 未选择项目 */}
            {!selectedProject && (
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  height: '400px',
                  color: 'var(--text-muted)',
                  gap: '16px',
                }}
              >
                <ArrowUpDown size={48} />
                <p>请选择一个项目来排序截图</p>
              </div>
            )}

            {/* 加载中 */}
            {selectedProject && loading && (
              <div
                style={{
                  display: 'flex',
                  height: '256px',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <div className="spinner" />
              </div>
            )}

            {/* 错误提示 */}
            {error && (
              <div
                style={{
                  padding: '12px 16px',
                  background: 'rgba(239, 68, 68, 0.2)',
                  color: 'var(--danger)',
                  borderRadius: '8px',
                  marginBottom: '16px',
                }}
              >
                {error}
              </div>
            )}

            {/* 已删除面板 */}
            <AnimatePresence>
              {showDeleted && deletedBatches.length > 0 && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  style={{
                    background: 'var(--bg-card)',
                    borderRadius: '8px',
                    marginBottom: '16px',
                    overflow: 'hidden',
                  }}
                >
                  <div style={{ padding: '16px' }}>
                    <h3
                      style={{
                        fontSize: '14px',
                        fontWeight: 600,
                        marginBottom: '12px',
                      }}
                    >
                      已删除的截图
                    </h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {deletedBatches.map((batch) => (
                        <div
                          key={batch.timestamp}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '8px 12px',
                            background: 'var(--bg-secondary)',
                            borderRadius: '6px',
                          }}
                        >
                          <span style={{ fontSize: '13px' }}>
                            {batch.count} 张截图 - {batch.timestamp}
                          </span>
                          <button
                            className="btn-ghost"
                            onClick={() =>
                              selectedProject && restoreBatch(selectedProject, batch.timestamp)
                            }
                            disabled={saving}
                            style={{ padding: '4px 8px', fontSize: '12px' }}
                          >
                            <RotateCcw size={12} />
                            恢复
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* 排序网格 */}
            {selectedProject && !loading && sortedScreenshots.length > 0 && (
              <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                onDragStart={handleDragStart}
                onDragEnd={handleDragEnd}
              >
                <SortableContext
                  items={sortedScreenshots.map((s) => s.filename)}
                  strategy={rectSortingStrategy}
                >
                  <div
                    ref={gridRef}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: `repeat(auto-fill, minmax(${getCardMinWidth(zoom)}px, 1fr))`,
                      gap: `${Math.round(10 * (zoom / 100))}px`,
                      position: 'relative',
                      transition: 'gap 200ms ease',
                    }}
                  >
                    {sortedScreenshots.map((screenshot, index) => (
                      <div key={screenshot.filename} style={{ position: 'relative' }}>
                        {/* 插入位置指示器 */}
                        {isDragOver && dropTargetIndex === index && (
                          <div
                            style={{
                              position: 'absolute',
                              left: '-6px',
                              top: 0,
                              bottom: 0,
                              width: '4px',
                              background: '#f59e0b',
                              borderRadius: '2px',
                              zIndex: 10,
                              boxShadow: '0 0 10px rgba(245, 158, 11, 0.8)',
                            }}
                          />
                        )}
                        <div data-screenshot-card>
                          <SortableScreenshot
                            screenshot={screenshot}
                            projectName={selectedProject}
                            index={index}
                            isSelected={selectedFiles.has(screenshot.filename)}
                            isNewlyAdded={screenshot.filename === newlyAdded}
                            onCardClick={(e) => handleCardClick(e, index, screenshot.filename)}
                            onboardingStart={onboardingRange.start}
                            onboardingEnd={onboardingRange.end}
                          />
                        </div>
                      </div>
                    ))}
                    {/* 末尾插入指示器 */}
                    {isDragOver && dropTargetIndex === sortedScreenshots.length && (
                      <div
                        style={{
                          position: 'absolute',
                          right: 0,
                          top: 0,
                          width: '4px',
                          height: '100%',
                          background: '#f59e0b',
                          borderRadius: '2px',
                          boxShadow: '0 0 10px rgba(245, 158, 11, 0.8)',
                        }}
                      />
                    )}
                  </div>
                </SortableContext>

                <DragOverlay dropAnimation={dropAnimation}>
                  {activeScreenshot && selectedProject && (
                    <DragPreview
                      screenshot={activeScreenshot}
                      projectName={selectedProject}
                      zoom={zoom}
                    />
                  )}
                </DragOverlay>
              </DndContext>
            )}

            {/* 空状态 */}
            {selectedProject && !loading && sortedScreenshots.length === 0 && (
              <div
                style={{
                  display: 'flex',
                  height: '256px',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--text-muted)',
                }}
              >
                该项目没有截图
              </div>
            )}
          </div>
        </div>

        {/* 右侧预览面板 */}
        {selectedProject && (
          <PreviewPanel
            screenshot={previewScreenshot}
            projectName={selectedProject}
            currentIndex={previewIndex !== null ? previewIndex : -1}
            total={sortedScreenshots.length}
            onClose={() => setPreviewIndex(null)}
            onPrev={prevPreview}
            onNext={nextPreview}
            onboardingStart={onboardingRange.start}
            onboardingEnd={onboardingRange.end}
          />
        )}
      </div>

      {/* 快捷键提示 */}
      {selectedProject && <ShortcutsHint />}

      {/* 底部浮动选择操作栏 */}
      <AnimatePresence>
        {selectedFiles.size > 0 && selectedProject && (
          <motion.div
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 50 }}
            transition={{ duration: 0.2, ease: [0.25, 1, 0.5, 1] }}
            style={{
              position: 'fixed',
              bottom: '24px',
              left: '50%',
              transform: 'translateX(-50%)',
              background: 'rgba(30, 30, 30, 0.95)',
              backdropFilter: 'blur(12px)',
              borderRadius: '12px',
              padding: '12px 20px',
              display: 'flex',
              alignItems: 'center',
              gap: '16px',
              boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(255,255,255,0.1)',
              zIndex: 1000,
            }}
          >
            <span style={{ 
              color: '#fff', 
              fontSize: '14px',
              fontWeight: 500,
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}>
              <CheckSquare size={18} style={{ color: '#3b82f6' }} />
              已选择 {selectedFiles.size} 张截图
            </span>
            
            <div style={{ width: '1px', height: '24px', background: 'rgba(255,255,255,0.2)' }} />
            
            <button
              onClick={deselectAll}
              style={{
                padding: '8px 16px',
                background: 'rgba(255,255,255,0.1)',
                border: 'none',
                borderRadius: '8px',
                color: '#fff',
                fontSize: '13px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                transition: 'background 150ms',
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.15)'}
              onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.1)'}
            >
              <X size={14} />
              取消选择
            </button>
            
            <button
              onClick={() => {
                const count = selectedFiles.size
                if (count > 10) {
                  if (window.confirm(`确定要删除 ${count} 张截图吗？此操作可以从"已删除"中恢复。`)) {
                    deleteSelected(selectedProject)
                  }
                } else {
                  deleteSelected(selectedProject)
                }
              }}
              disabled={saving}
              style={{
                padding: '8px 16px',
                background: '#ef4444',
                border: 'none',
                borderRadius: '8px',
                color: '#fff',
                fontSize: '13px',
                cursor: saving ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                opacity: saving ? 0.6 : 1,
                transition: 'background 150ms, opacity 150ms',
              }}
              onMouseEnter={(e) => !saving && (e.currentTarget.style.background = '#dc2626')}
              onMouseLeave={(e) => e.currentTarget.style.background = '#ef4444'}
            >
              <Trash2 size={14} />
              删除选中
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </AppLayout>
  )
}
