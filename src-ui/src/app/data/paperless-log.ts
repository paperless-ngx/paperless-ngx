export const DEBUG = 10
export const INFO = 20
export const WARNING = 30
export const ERROR = 40
export const CRITICAL = 50

export const LOG_LEVELS = [
  {id: DEBUG, name: "DEBUG"},
  {id: INFO, name: "INFO"},
  {id: WARNING, name: "WARNING"},
  {id: ERROR, name: "ERROR"},
  {id: CRITICAL, name: "CRITICAL"}
]

export interface PaperlessLog {

  id?: number

  group?: string

  message?: string

  created?: Date

  level?: number

}
