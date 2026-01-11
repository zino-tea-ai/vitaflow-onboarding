'use client'

import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

// 用户在 Onboarding 中收集的所有数据
export interface UserData {
  // 姓名（用于个性化称呼）
  name: string | null
  
  // 基础目标
  goal: 'lose_weight' | 'build_muscle' | 'maintain_weight' | null
  
  // 个人信息
  gender: 'female' | 'male' | 'other' | null
  age: number | null
  
  // 身体数据
  currentWeight: number | null
  targetWeight: number | null
  height: number | null
  weeklyLossRate: 0.5 | 1 | 1.5 | null  // 每周减重速度 (kg)
  
  // 运动习惯
  activityLevel: 'sedentary' | 'light' | 'moderate' | 'active' | null
  workoutFrequency: 'rarely' | 'sometimes' | 'often' | null
  
  // 伏笔问题
  acquisitionChannel: string | null
  previousAppExperience: 'yes' | 'no' | null
  previousBarriers: string[] | null
  dietaryPreferences: string[] | null
  secondaryGoals: string[] | null
  
  // 权限
  healthKitConnected: boolean
  notificationsEnabled: boolean
  trackingAllowed: boolean
  
  // 其他
  referralCode: string | null
}

// 计算结果（基于用户数据）
export interface CalculatedResults {
  dailyCalories: number
  targetDate: string
  weeklyLoss: number
  bmi: number
  tdee: number
  // 三大营养素 (grams)
  protein: number
  carbs: number
  fat: number
}

interface OnboardingState {
  // 当前步骤
  currentStep: number
  totalSteps: number
  
  // 单位系统
  unitSystem: 'metric' | 'imperial'
  
  // 用户数据
  userData: UserData
  
  // 计算结果
  results: CalculatedResults | null
  
  // 游戏状态
  scanGameCompleted: boolean
  spinAttempts: number
  discountWon: number | null
  
  // 付款状态
  paymentCompleted: boolean
  selectedPlan: 'weekly' | 'monthly' | 'yearly' | null
  
  // 动画控制
  direction: 1 | -1 // 1: forward, -1: backward
  
  // 手动导航标志（用于禁用自动跳转）
  isManualNavigation: boolean
  
  // V3 新增：动画状态
  animationState: 'idle' | 'transitioning' | 'animating'
  
  // V3 新增：用户行为追踪
  behaviorTracking: {
    pageViewTimes: Record<number, number>  // 页面ID -> 停留时间(ms)
    interactions: Array<{
      pageId: number
      action: string
      timestamp: number
    }>
  }
  
  // V3 新增：里程碑完成状态
  milestonesCompleted: string[]  // 已完成的阶段ID列表
  
  // Actions
  nextStep: () => void
  prevStep: () => void
  goToStep: (step: number) => void
  clearManualNavigation: () => void
  setUserData: <K extends keyof UserData>(key: K, value: UserData[K]) => void
  setResults: (results: CalculatedResults) => void
  completeScanGame: () => void
  spinWheel: () => number // 返回获得的折扣
  completePayment: (plan: 'weekly' | 'monthly' | 'yearly') => void
  resetDemo: () => void
  setTotalSteps: (total: number) => void  // A/B Test 用
  setUnitSystem: (system: 'metric' | 'imperial') => void
  
  // V3 新增 Actions
  setAnimationState: (state: 'idle' | 'transitioning' | 'animating') => void
  trackPageView: (pageId: number, duration: number) => void
  trackInteraction: (pageId: number, action: string) => void
  completeMilestone: (phaseId: string) => void
}

const initialUserData: UserData = {
  name: null,
  goal: null,
  gender: null,
  age: null,
  currentWeight: null,
  targetWeight: null,
  height: null,
  weeklyLossRate: null,
  activityLevel: null,
  workoutFrequency: null,
  acquisitionChannel: null,
  previousAppExperience: null,
  previousBarriers: null,
  dietaryPreferences: null,
  secondaryGoals: null,
  healthKitConnected: false,
  notificationsEnabled: false,
  trackingAllowed: false,
  referralCode: null,
}

export const useOnboardingStore = create<OnboardingState>()(
  persist(
    (set, get) => ({
      currentStep: 1,
      totalSteps: 37,
      unitSystem: 'metric' as const,
      userData: initialUserData,
      results: null,
      scanGameCompleted: false,
      spinAttempts: 0,
      discountWon: null,
      paymentCompleted: false,
      selectedPlan: null,
      direction: 1,
      isManualNavigation: false,
      animationState: 'idle',
      behaviorTracking: {
        pageViewTimes: {},
        interactions: []
      },
      milestonesCompleted: [],
      
      nextStep: () => {
        set((state) => ({
          currentStep: Math.min(state.currentStep + 1, state.totalSteps),
          direction: 1,
          isManualNavigation: false
        }));
      },
      
      prevStep: () => {
        set((state) => ({
          currentStep: Math.max(state.currentStep - 1, 1),
          direction: -1,
          isManualNavigation: false
        }));
      },
      
      goToStep: (step) => {
        set((state) => ({
          currentStep: Math.max(1, Math.min(step, state.totalSteps)),
          direction: step > state.currentStep ? 1 : -1,
          isManualNavigation: true
        }));
      },
      
      clearManualNavigation: () => set({ isManualNavigation: false }),
      
      setUserData: (key, value) => set((state) => ({
        userData: { ...state.userData, [key]: value }
      })),
      
      setResults: (results) => set({ results }),
      
      completeScanGame: () => set({ scanGameCompleted: true }),
      
      spinWheel: () => {
        const { spinAttempts } = get()
        let discount: number
        
        if (spinAttempts === 0) {
          // 第一次：故意不中大奖，给个小奖或"再试一次"
          const smallPrizes = [10, 15, 20, 0] // 0 表示"再试一次"
          discount = smallPrizes[Math.floor(Math.random() * smallPrizes.length)]
        } else {
          // 第二次：必中 50%
          discount = 50
        }
        
        set((state) => ({
          spinAttempts: state.spinAttempts + 1,
          discountWon: discount > 0 ? discount : state.discountWon
        }))
        
        return discount
      },
      
      completePayment: (plan) => set({
        paymentCompleted: true,
        selectedPlan: plan
      }),
      
      resetDemo: () => set({
        currentStep: 1,
        unitSystem: 'metric',
        userData: initialUserData,
        results: null,
        scanGameCompleted: false,
        spinAttempts: 0,
        discountWon: null,
        paymentCompleted: false,
        selectedPlan: null,
        direction: 1,
        isManualNavigation: false
      }),
      
      setTotalSteps: (total) => set({ totalSteps: total }),
      
      setUnitSystem: (system) => set({ unitSystem: system }),
      
      // V3 新增 Actions
      setAnimationState: (state) => set({ animationState: state }),
      
      trackPageView: (pageId, duration) => set((state) => ({
        behaviorTracking: {
          ...state.behaviorTracking,
          pageViewTimes: {
            ...state.behaviorTracking.pageViewTimes,
            [pageId]: duration
          }
        }
      })),
      
      trackInteraction: (pageId, action) => set((state) => ({
        behaviorTracking: {
          ...state.behaviorTracking,
          interactions: [
            ...state.behaviorTracking.interactions,
            {
              pageId,
              action,
              timestamp: Date.now()
            }
          ]
        }
      })),
      
      completeMilestone: (phaseId) => set((state) => ({
        milestonesCompleted: state.milestonesCompleted.includes(phaseId)
          ? state.milestonesCompleted
          : [...state.milestonesCompleted, phaseId]
      }))
    }),
    {
      name: 'vitaflow-onboarding-demo',
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({
        currentStep: state.currentStep,
        unitSystem: state.unitSystem,
        userData: state.userData,
        results: state.results,
        scanGameCompleted: state.scanGameCompleted,
        spinAttempts: state.spinAttempts,
        discountWon: state.discountWon,
        paymentCompleted: state.paymentCompleted,
        selectedPlan: state.selectedPlan,
      })
    }
  )
)

// 计算用户的个性化结果
export function calculateResults(userData: UserData): CalculatedResults | null {
  const { currentWeight, targetWeight, height, age, gender, activityLevel } = userData
  
  if (!currentWeight || !height || !age || !gender || !activityLevel) {
    return null
  }
  
  // BMR 计算 (Mifflin-St Jeor 公式)
  let bmr: number
  if (gender === 'male') {
    bmr = 10 * currentWeight + 6.25 * height - 5 * age + 5
  } else {
    bmr = 10 * currentWeight + 6.25 * height - 5 * age - 161
  }
  
  // 活动系数
  const activityMultipliers = {
    sedentary: 1.2,
    light: 1.375,
    moderate: 1.55,
    active: 1.725
  }
  
  const tdee = Math.round(bmr * activityMultipliers[activityLevel])
  
  // 计算每日目标卡路里
  let dailyCalories = tdee
  const weightDiff = (targetWeight || currentWeight) - currentWeight
  
  if (weightDiff < 0) {
    // 减重：每周减 0.5kg，需要每天赤字 550 卡
    dailyCalories = tdee - 550
  } else if (weightDiff > 0) {
    // 增重：每天增加 300-500 卡
    dailyCalories = tdee + 400
  }
  
  // 计算达到目标的预计日期
  const weeksNeeded = Math.abs(weightDiff) / 0.5
  const targetDate = new Date()
  targetDate.setDate(targetDate.getDate() + weeksNeeded * 7)
  
  // BMI
  const heightInM = height / 100
  const bmi = Math.round((currentWeight / (heightInM * heightInM)) * 10) / 10
  
  // 三大营养素计算
  const finalCalories = Math.max(1200, Math.round(dailyCalories))
  
  // 蛋白质：减重时高蛋白 (30%)，增重时中等 (25%)，维持时标准 (20%)
  // 碳水：减重时低碳 (40%)，增重时高碳 (50%)，维持时标准 (50%)
  // 脂肪：填充剩余热量
  let proteinRatio: number
  let carbsRatio: number
  
  if (weightDiff < 0) {
    // 减重
    proteinRatio = 0.30
    carbsRatio = 0.40
  } else if (weightDiff > 0) {
    // 增重
    proteinRatio = 0.25
    carbsRatio = 0.50
  } else {
    // 维持
    proteinRatio = 0.20
    carbsRatio = 0.50
  }
  
  const fatRatio = 1 - proteinRatio - carbsRatio
  
  // 蛋白质和碳水：1g = 4kcal，脂肪：1g = 9kcal
  const protein = Math.round((finalCalories * proteinRatio) / 4)
  const carbs = Math.round((finalCalories * carbsRatio) / 4)
  const fat = Math.round((finalCalories * fatRatio) / 9)
  
  return {
    dailyCalories: finalCalories,
    targetDate: targetDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }),
    weeklyLoss: weightDiff < 0 ? 0.5 : (weightDiff > 0 ? 0.3 : 0),
    bmi,
    tdee,
    protein,
    carbs,
    fat
  }
}







