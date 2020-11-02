export const LOG_LEVEL_DEBUG = 10
export const LOG_LEVEL_INFO = 20
export const LOG_LEVEL_WARNING = 30
export const LOG_LEVEL_ERROR = 40
export const LOG_LEVEL_CRITICAL = 50

export const LOG_LEVELS = [
  {id: LOG_LEVEL_DEBUG, name: "DEBUG"},
  {id: LOG_LEVEL_INFO, name: "INFO"},
  {id: LOG_LEVEL_WARNING, name: "WARNING"},
  {id: LOG_LEVEL_ERROR, name: "ERROR"},
  {id: LOG_LEVEL_CRITICAL, name: "CRITICAL"}
]

export interface PaperlessLog {

  id?: number

  group?: string

  message?: string

  created?: Date

  level?: number

}
