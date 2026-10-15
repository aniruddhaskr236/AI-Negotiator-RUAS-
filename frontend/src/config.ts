const mockSetting =
  import.meta.env.USE_MOCK ?? import.meta.env.VITE_USE_MOCK

export const USE_MOCK = mockSetting === undefined || mockSetting !== "false"
export const REPOSITORY_URL =
  import.meta.env.VITE_REPOSITORY_URL || "#built-with"
