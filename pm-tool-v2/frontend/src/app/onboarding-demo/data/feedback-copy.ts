/**
 * VitaFlow Conversational Onboarding - Feedback Copy Library
 * 
 * Three styles:
 * - witty: Playful and clever (Brilliant style)
 * - warm: Warm and encouraging
 * - data: Data-driven
 * 
 * Usage:
 * const copy = getFeedbackCopy('goal_lose_weight', 'witty')
 */

export type CopyStyle = 'witty' | 'warm' | 'data'

export interface FeedbackCopyItem {
  witty: string
  warm: string
  data: string
}

// ============ Introduction Copy ============
export const introductionCopy: Record<string, FeedbackCopyItem[]> = {
  // Character introduction (sequence)
  greeting: [
    {
      witty: "Hey there! 👋",
      warm: "Hi! I'm Vita 👋",
      data: "Hello! I'm Vita.",
    },
    {
      witty: "I'm Vita, your AI nutrition sidekick.",
      warm: "I'll be with you every step of the way on your health journey.",
      data: "Your AI-powered nutrition assistant.",
    },
    {
      witty: "Think of me as your pocket nutritionist... minus the boring lectures.",
      warm: "Let's make this fun and simple!",
      data: "Let's analyze your goals and build a personalized plan.",
    },
  ],
  
  // Start button copy
  start_button: [
    {
      witty: "Let's do this! 💪",
      warm: "Let's Get Started!",
      data: "Start Analysis",
    },
  ],
}

// ============ Page Title/Question Copy ============
export const pageTitleCopy: Record<string, FeedbackCopyItem> = {
  // Welcome page
  welcome: {
    witty: "Let's build a health path just for you.",
    warm: "Let's start your health journey!",
    data: "AI-powered nutrition tracking begins",
  },
  
  // Name input
  name_input: {
    witty: "What should I call you?",
    warm: "What's your name?",
    data: "Enter your name to personalize",
  },
  
  // Goal selection
  goal_selection: {
    witty: "What's your top goal?",
    warm: "Choose the goal you want to achieve",
    data: "Select goal to optimize recommendations",
  },
  
  // Gender selection
  gender_selection: {
    witty: "Quick question for the algorithm...",
    warm: "This helps us understand you better",
    data: "Gender affects metabolism calculation",
  },
  
  // Age input
  age_input: {
    witty: "How many trips around the sun?",
    warm: "How old are you?",
    data: "Age is used to calculate BMR",
  },
  
  // Height & Weight
  height_weight: {
    witty: "Time for the numbers. No judgment here.",
    warm: "Let's get your body measurements",
    data: "Height & weight for BMI and TDEE",
  },
  
  // Target weight
  target_weight: {
    witty: "Where do you want to be?",
    warm: "Set a healthy, achievable goal",
    data: "Target weight determines calorie deficit",
  },
  
  // Activity level
  activity_level: {
    witty: "How much do you move? Be honest! 😅",
    warm: "This helps us personalize your calorie needs.",
    data: "Activity level affects TDEE calculation by 20-40%.",
  },
  
  // Time preference
  time_preference: {
    witty: "How will learning fit into your day?",
    warm: "When would you like reminders?",
    data: "Select optimal reminder time",
  },
  
  // Result page
  result_page: {
    witty: "You'll fit right in.",
    warm: "Your personalized plan is ready!",
    data: "Here's your data analysis",
  },
  
  // Value prop - AI Scan
  value_ai_scan: {
    witty: "Point. Shoot. Know everything. Magic? Nope, just AI.",
    warm: "Taking a photo is all it takes! I'll handle the rest.",
    data: "98% accuracy. 0.3s scan time. 500K+ meals logged daily.",
  },
  
  // Value prop - Personalized
  value_personalized: {
    witty: "I'm like a nutritionist... but I never sleep. And I'm free!",
    warm: "Every suggestion is tailored to your unique goals.",
    data: "Personalized plans show 2x higher goal completion rates.",
  },
  
  // Permission - Notification
  permission_notification: {
    witty: "I promise not to spam! Just helpful nudges when you need them.",
    warm: "Gentle reminders to keep you on track.",
    data: "Users with notifications enabled reach goals 67% faster.",
  },
  
  // Permission - Health
  permission_health: {
    witty: "Let's sync up! More data = better results.",
    warm: "Connecting helps me give you better insights.",
    data: "Health sync improves calorie accuracy by 23%.",
  },
  
  // Complete
  complete: {
    witty: "You're officially ready to crush it! 🚀",
    warm: "You're all set! Let's start your journey!",
    data: "Setup complete. Ready to begin tracking.",
  },
  
  // Value prop (general)
  value_prop: {
    witty: "Learn 6x more effectively.",
    warm: "How VitaFlow helps you succeed",
    data: "Science-backed nutrition tracking",
  },
  
  // Celebration
  celebration: {
    witty: "You're on your way!",
    warm: "Amazing! You're doing great!",
    data: "Setup complete, ready to track",
  },
}

// ============ Option Feedback Copy ============
export const optionFeedbackCopy: Record<string, FeedbackCopyItem> = {
  // Goal selection
  goal_lose_weight: {
    witty: "Watch out, fat. Here comes trouble. 💪",
    warm: "Great choice! Weight loss is a great start",
    data: "Expected: lose 5-8kg in 12 weeks",
  },
  goal_build_muscle: {
    witty: "Future you is already flexing. 🏆",
    warm: "Great goal! Let's get stronger together",
    data: "Expected: gain 0.5-1kg muscle per month",
  },
  goal_maintain: {
    witty: "Balance is a superpower. Respect. ⚖️",
    warm: "Maintaining is awesome too!",
    data: "Maintain mode: stay within ±1kg range",
  },
  
  // Gender selection
  gender_male: {
    witty: "Got it! That affects the math.",
    warm: "Got it!",
    data: "Male avg BMR: 1600-1800 kcal",
  },
  gender_female: {
    witty: "Noted! Adjusting calculations...",
    warm: "Understood!",
    data: "Female avg BMR: 1200-1400 kcal",
  },
  gender_other: {
    witty: "All good! We'll make it work.",
    warm: "No problem!",
    data: "Using neutral metabolism formula",
  },
  
  // Time preference
  time_morning: {
    witty: "Breakfast of champions? You got it.",
    warm: "Early bird! Start your day energized",
    data: "Breakfast logging has 23% higher success",
  },
  time_lunch: {
    witty: "Midday fuel check. Smart move.",
    warm: "Lunch time! Remember to eat well",
    data: "Lunch is key for calorie control",
  },
  time_dinner: {
    witty: "Dinner dates with your health. Romantic.",
    warm: "End your day right, treat yourself",
    data: "Dinner is 35-40% of daily calories",
  },
  time_night: {
    witty: "Source code by starlight. Sounds dreamy.",
    warm: "Night owl? Watch your nutrition!",
    data: "Night eating affects sleep quality",
  },
  
  // Activity level
  activity_sedentary: {
    witty: "Desk life? We'll account for that.",
    warm: "Desk job? We'll adjust for you",
    data: "Activity factor: 1.2 (sedentary)",
  },
  activity_light: {
    witty: "A little movement goes a long way!",
    warm: "Light exercise is great! Keep it up",
    data: "Activity factor: 1.375 (light)",
  },
  activity_moderate: {
    witty: "Active lifestyle detected. Nice!",
    warm: "Your exercise habits are healthy!",
    data: "Activity factor: 1.55 (moderate)",
  },
  activity_active: {
    witty: "Athlete mode activated! 🔥",
    warm: "Fitness pro! Amazing!",
    data: "Activity factor: 1.725 (active)",
  },
  
  // Workout frequency
  workout_rarely: {
    witty: "Starting from zero is still starting.",
    warm: "That's okay, let's start together",
    data: "Suggest: start with 2-3x per week",
  },
  workout_sometimes: {
    witty: "Occasional warrior. Respect!",
    warm: "Occasional exercise is good!",
    data: "Current frequency maintains health",
  },
  workout_often: {
    witty: "Gym rat detected! 💪",
    warm: "Fitness enthusiast! You're amazing!",
    data: "High frequency = 20-30% more calories",
  },
  
  // Weight loss pace
  pace_slow: {
    witty: "Slow and steady wins the race.",
    warm: "Steady progress, healthy results",
    data: "0.5kg/week, goal in 16 weeks",
  },
  pace_moderate: {
    witty: "Finding the sweet spot. Nice!",
    warm: "Balanced choice!",
    data: "0.75kg/week, goal in 12 weeks",
  },
  pace_fast: {
    witty: "Full speed ahead! Let's go!",
    warm: "Sprint mode activated!",
    data: "1kg/week, goal in 8 weeks",
  },
}

// ============ Input Feedback ============
export const inputFeedbackCopy: Record<string, (value: number) => FeedbackCopyItem> = {
  // Age input
  age: (age: number) => ({
    witty: age < 25 
      ? "Youth is on your side!" 
      : age < 40 
        ? "Prime time for change!"
        : "Experience is a superpower!",
    warm: age < 25 
      ? "Youth is your advantage!" 
      : age < 40 
        ? "Perfect time for change!"
        : "It's never too late to start!",
    data: `Age ${age}: BMR is ${age < 30 ? 'higher' : age < 50 ? 'moderate' : 'needs attention'}`,
  }),
  
  // Height input
  height: (height: number) => ({
    witty: height > 180 
      ? "Looking up to you already!" 
      : height > 165 
        ? "Perfect height for greatness!"
        : "Good things come in all sizes!",
    warm: "Recorded!",
    data: `Height ${height}cm: ideal weight ${Math.round(height - 105)}-${Math.round(height - 95)}kg`,
  }),
  
  // Weight input
  weight: (weight: number) => ({
    witty: "Brave move. The scale is just a number.",
    warm: "Thanks for trusting us, let's do this together",
    data: `Current weight ${weight}kg recorded`,
  }),
  
  // Target weight input - 需要结合当前体重计算差值
  // 这里只能拿到 target，差值逻辑在组件里处理
  targetWeight: (target: number) => ({
    witty: "Got it! I'll build your plan around this.",
    warm: "Great goal! We'll get there together.",
    data: "Target set. Calculating your plan.",
  }),
}

// ============ Phase Completion Copy ============
export const phaseCompletionCopy: Record<string, FeedbackCopyItem> = {
  profile_complete: {
    witty: "Phase 1: Complete. You're on fire! 🔥",
    warm: "Phase 1 complete! You're doing great!",
    data: "Profile collected, starting analysis",
  },
  setup_complete: {
    witty: "All systems go! Ready for launch! 🚀",
    warm: "Setup complete! Ready for your journey",
    data: "Initialization complete, data synced",
  },
  first_scan_complete: {
    witty: "First scan in the books! You're a natural!",
    warm: "First scan success! You're a quick learner!",
    data: "First AI scan complete, improving accuracy",
  },
}

// ============ Transition/Value Page Copy ============
export const transitionCopy: Record<string, FeedbackCopyItem> = {
  calculating: {
    witty: "Crunching the numbers... This is exciting!",
    warm: "Creating your personalized plan...",
    data: "Processing data, ~3 seconds",
  },
  analyzing: {
    witty: "Your data is telling a story...",
    warm: "Analyzing your data...",
    data: "AI model analyzing",
  },
  creating_plan: {
    witty: "Crafting your personalized journey...",
    warm: "Creating your custom plan...",
    data: "Generating personalized plan",
  },
  almost_done: {
    witty: "Almost there... Good things take time!",
    warm: "Almost done!",
    data: "95% complete",
  },
  ready: {
    witty: "Boom! Your plan is ready!",
    warm: "Done! Your plan is ready!",
    data: "Plan generation complete",
  },
  
  // Value props
  value_social_proof: {
    witty: "You'll fit right in.",
    warm: "500K+ users have started their journey",
    data: "Users reach goals in 12 weeks, 78% success",
  },
  value_effectiveness: {
    witty: "Learn 6x more effectively.",
    warm: "AI helps you track nutrition efficiently",
    data: "95%+ AI accuracy, saves 80% logging time",
  },
  value_habit: {
    witty: "Smarter every day.",
    warm: "Progress a little each day",
    data: "21 days to form habits, VitaFlow helps",
  },
}

// ============ Error/Empty State Copy ============
export const errorCopy: Record<string, FeedbackCopyItem> = {
  empty_name: {
    witty: "I need something to call you!",
    warm: "Please enter your name",
    data: "Name field cannot be empty",
  },
  invalid_weight: {
    witty: "That doesn't quite add up...",
    warm: "Please enter a valid weight",
    data: "Weight should be 30-200kg",
  },
  network_error: {
    witty: "Oops! The internet took a coffee break.",
    warm: "Network issue, please try again",
    data: "Network failed, check connection",
  },
}

// ============ Utility Functions ============

/**
 * Get option feedback copy
 */
export function getOptionFeedback(optionKey: string, style: CopyStyle): string {
  const copy = optionFeedbackCopy[optionKey]
  if (!copy) return ''
  return copy[style]
}

/**
 * Get page title copy
 */
export function getPageTitle(pageKey: string, style: CopyStyle): string {
  const copy = pageTitleCopy[pageKey]
  if (!copy) return ''
  return copy[style]
}

/**
 * Get input feedback copy
 */
export function getInputFeedback(inputKey: string, value: number, style: CopyStyle): string {
  const copyFn = inputFeedbackCopy[inputKey]
  if (!copyFn) return ''
  return copyFn(value)[style]
}

/**
 * Get transition copy
 */
export function getTransitionCopy(transitionKey: string, style: CopyStyle): string {
  const copy = transitionCopy[transitionKey]
  if (!copy) return ''
  return copy[style]
}

/**
 * Get phase completion copy
 */
export function getPhaseCopy(phaseKey: string, style: CopyStyle): string {
  const copy = phaseCompletionCopy[phaseKey]
  if (!copy) return ''
  return copy[style]
}

/**
 * Generate feedback key from option ID
 */
export function optionIdToFeedbackKey(storeKey: string, optionId: string): string {
  // 映射 storeKey 到 feedback key 前缀
  const keyMapping: Record<string, string> = {
    activityLevel: 'activity',
    workoutFrequency: 'workout',
    weightPace: 'pace',
    preferredTime: 'time',
    // 其他直接用 storeKey
  }
  
  const prefix = keyMapping[storeKey] || storeKey
  return `${prefix}_${optionId}`
}

/**
 * Get introduction copy
 */
export function getIntroductionCopy(key: string, index: number, style: CopyStyle): string {
  const copyArray = introductionCopy[key]
  if (!copyArray || !copyArray[index]) return ''
  return copyArray[index][style]
}

/**
 * Get all introduction copy (by style)
 */
export function getAllIntroductionCopy(key: string, style: CopyStyle): string[] {
  const copyArray = introductionCopy[key]
  if (!copyArray) return []
  return copyArray.map(item => item[style])
}
