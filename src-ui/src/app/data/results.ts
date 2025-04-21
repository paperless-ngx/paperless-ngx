export interface Results<T> {
  count: number

  results: T[]

  all: number[]

  previous?: string

  next?: string
}
